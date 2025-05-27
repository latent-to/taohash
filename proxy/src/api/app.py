"""
FastAPI application for TaoHash mining statistics API.

Provides RESTful endpoints for querying mining pool and worker statistics.
"""

import os
import time
from typing import Any, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from ..storage.db import StatsDB
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)


app = FastAPI(
    title="TaoHash Mining API",
    description="API for querying mining pool and worker statistics",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

security = HTTPBearer()

API_TOKENS = set(
    token.strip()
    for token in os.environ.get("API_TOKENS", "").split(",")
    if token.strip()
)

db: Optional[StatsDB] = None


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """Verify API token."""
    token = credentials.credentials
    if not API_TOKENS or token not in API_TOKENS:
        raise HTTPException(status_code=403, detail="Invalid API token")
    return token


@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup."""
    global db
    db = StatsDB()
    if await db.init():
        logger.info("API connected to ClickHouse successfully")
    else:
        logger.warning("API running without database connection")


@app.get("/health")
async def health_check():
    """Health check endpoint (no auth required)."""
    return {
        "status": "ok",
        "timestamp": int(time.time()),
        "database": "connected" if db and db.client else "disconnected",
    }


@app.get("/api/pool/stats")
@limiter.limit("60/minute")
async def get_pool_stats(
    request: Request, token: str = Depends(verify_token)
) -> dict[str, Any]:
    """
    Get pool-wide statistics.

    Returns statistics for 5-minute, 60-minute, and 24-hour windows.
    """
    if not db or not db.client:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        now = datetime.now()
        yesterday = now - timedelta(days=1)

        stats_5m = await _get_pool_stats_for_window("5m")
        stats_60m = await _get_pool_stats_for_window("60m")
        stats_24h = await _get_pool_stats_for_window("24h")
        stats_yesterday = await _get_pool_stats_yesterday(yesterday)

        worker_counts = await _get_worker_counts()
        username = os.environ.get("POOL_USER", "proxy_user")

        return {
            "username": username,
            "btc": {
                "all_time_reward": "0.00000000",  # TODO
                "hash_rate_unit": "Gh/s",
                "hash_rate_5m": round(stats_5m.get("hashrate", 0) / 1e9)
                if stats_5m.get("hashrate", 0)
                else 0,  # Convert to GH/s
                "hash_rate_60m": round(stats_60m.get("hashrate", 0) / 1e9)
                if stats_60m.get("hashrate", 0)
                else 0,
                "hash_rate_24h": round(stats_24h.get("hashrate", 0) / 1e9)
                if stats_24h.get("hashrate", 0)
                else 0,
                "hash_rate_yesterday": round(stats_yesterday.get("hashrate", 0) / 1e9)
                if stats_yesterday.get("hashrate", 0)
                else 0,
                "low_workers": 0,
                "off_workers": worker_counts.get("off_workers", 0),
                "ok_workers": worker_counts.get("ok_workers", 0),
                "dis_workers": 0,
                "current_balance": "0.00000000",  # TODO
                "today_reward": "0.00000000",  # TODO
                "estimated_reward": "0.00000000",  # TODO
                "shares_5m": stats_5m.get("total_shares", 0),
                "shares_60m": stats_60m.get("total_shares", 0),
                "shares_24h": stats_24h.get("total_shares", 0),
                "shares_yesterday": stats_yesterday.get("total_shares", 0),
                "shares_value_5m": stats_5m.get("share_value", 0),
                "shares_value_60m": stats_60m.get("share_value", 0),
                "shares_value_24h": stats_24h.get("share_value", 0),
                "shares_value_yesterday": stats_yesterday.get("share_value", 0),
            },
        }

    except Exception as e:
        logger.error(f"Error fetching pool stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/workers/stats")
@limiter.limit("60/minute")
async def get_workers_stats(
    request: Request,
    token: str = Depends(verify_token),
    miner: Optional[str] = None,
    worker: Optional[str] = None,
) -> dict[str, Any]:
    """
    Get per-worker statistics.

    Can filter by specific miner/worker if provided.
    """
    if not db or not db.client:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        workers = await _get_worker_stats(miner, worker)

        workers_dict = {}
        for w in workers:
            worker_key = w["worker"]
            workers_dict[worker_key] = {
                "state": w.get("state", "ok"),
                "last_share": int(w.get("last_share_ts", 0)),
                "hash_rate_unit": "Gh/s",
                "hash_rate_scoring": 0,
                "hash_rate_5m": w.get("hashrate_5m", 0) / 1e9,
                "hash_rate_60m": w.get("hashrate_60m", 0) / 1e9,
                "hash_rate_24h": w.get("hashrate_24h", 0) / 1e9,
                "shares_5m": w.get("shares_5m", 0),
                "shares_60m": w.get("shares_60m", 0),
                "shares_24h": w.get("shares_24h", 0),
                "share_value_5m": w.get("share_value_5m", 0),
                "share_value_60m": w.get("share_value_60m", 0),
                "share_value_24h": w.get("share_value_24h", 0),
            }

        return {"btc": {"workers": workers_dict}}

    except Exception as e:
        logger.error(f"Error fetching worker stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def _get_pool_stats_for_window(window: str) -> dict[str, Any]:
    """Get pool statistics for a specific time window using the new views."""
    try:
        view_name = f"pool_stats_{window}"
        query = f"""
        SELECT 
            active_workers,
            shares,
            shares as accepted,  -- All shares are accepted
            0 as rejected,      -- No rejected shares
            pool_difficulty_sum,
            actual_difficulty_sum as share_value,
            hashrate
        FROM {view_name}
        """

        result = await db.client.query(query)

        if result.result_rows and result.result_rows[0]:
            row = result.result_rows[0]
            return {
                "active_workers": int(row[0] or 0),
                "total_shares": int(row[1] or 0),
                "accepted": int(row[2] or 0),
                "rejected": int(row[3] or 0),
                "total_difficulty": float(row[4] or 0),
                "share_value": float(row[5] or 0),
                "hashrate": float(row[6] or 0) if row[6] else 0,
            }
    except Exception as e:
        logger.error(f"Error in _get_pool_stats_for_window: {e}")

    return {
        "active_workers": 0,
        "total_shares": 0,
        "accepted": 0,
        "rejected": 0,
        "total_difficulty": 0,
        "hashrate": 0,
        "share_value": 0,
    }


async def _get_pool_stats_yesterday(yesterday: datetime) -> dict[str, Any]:
    """Get pool statistics for yesterday."""
    try:
        query = """
        SELECT 
            count(DISTINCT worker) as active_workers,
            count() as total_shares,
            count() as accepted,  -- All shares are accepted
            0 as rejected,        -- No rejected shares
            sum(pool_difficulty) as total_difficulty,
            sum(actual_difficulty) as share_value,
            sum(pool_difficulty) * 4294967296 / 86400 as hashrate
        FROM shares
        WHERE ts >= %(start)s AND ts < %(end)s
        """

        result = await db.client.query(
            query,
            parameters={
                "start": yesterday.replace(hour=0, minute=0, second=0, microsecond=0),
                "end": yesterday.replace(
                    hour=23, minute=59, second=59, microsecond=999999
                ),
            },
        )

        if result.result_rows and result.result_rows[0]:
            row = result.result_rows[0]
            return {
                "active_workers": int(row[0] or 0),
                "total_shares": int(row[1] or 0),
                "accepted": int(row[2] or 0),
                "rejected": int(row[3] or 0),
                "total_difficulty": float(row[4] or 0),
                "share_value": float(row[5] or 0),
                "hashrate": float(row[6] or 0) if row[6] else 0,
            }
    except Exception as e:
        logger.error(f"Error in _get_pool_stats_yesterday: {e}")

    return {
        "active_workers": 0,
        "total_shares": 0,
        "accepted": 0,
        "rejected": 0,
        "total_difficulty": 0,
        "hashrate": 0,
        "share_value": 0,
    }


async def _get_worker_counts() -> dict[str, int]:
    """Get counts of workers in different states."""
    try:
        query = """
        SELECT 
            sum(CASE WHEN last_share_ts > now() - INTERVAL 2 HOUR THEN 1 ELSE 0 END) as ok_workers,
            sum(CASE WHEN last_share_ts <= now() - INTERVAL 2 HOUR THEN 1 ELSE 0 END) as off_workers
        FROM worker_state
        """

        result = await db.client.query(query)

        if result.result_rows and result.result_rows[0]:
            row = result.result_rows[0]
            return {"ok_workers": int(row[0] or 0), "off_workers": int(row[1] or 0)}
    except Exception as e:
        logger.error(f"Error in _get_worker_counts: {e}")

    return {"ok_workers": 0, "off_workers": 0}


async def _get_worker_stats(
    miner: Optional[str] = None, worker: Optional[str] = None
) -> list[dict[str, Any]]:
    """Get worker statistics with optional filtering."""
    where_conditions = []
    params = {}

    if miner:
        where_conditions.append("miner = %(miner)s")
        params["miner"] = miner
    if worker:
        where_conditions.append("worker = %(worker)s")
        params["worker"] = worker

    where_clause = f"AND {' AND '.join(where_conditions)}" if where_conditions else ""
    where_clause_standalone = (
        f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
    )

    query = f"""
    WITH 
    -- 5-minute stats directly from shares
    stats_5m AS (
        SELECT 
            miner, worker,
            count() as shares,
            sum(actual_difficulty) as share_value,
            sum(pool_difficulty) * 4294967296 / 300 as hashrate
        FROM shares
        WHERE ts > now() - INTERVAL 5 MINUTE
        {where_clause}
        GROUP BY miner, worker
    ),
    -- 60-minute stats directly from shares
    stats_60m AS (
        SELECT 
            miner, worker,
            count() as shares,
            sum(actual_difficulty) as share_value,
            sum(pool_difficulty) * 4294967296 / 3600 as hashrate
        FROM shares
        WHERE ts > now() - INTERVAL 60 MINUTE
        {where_clause}
        GROUP BY miner, worker
    ),
    -- 24-hour stats directly from shares
    stats_24h AS (
        SELECT 
            miner, worker,
            count() as shares,
            sum(actual_difficulty) as share_value,
            sum(pool_difficulty) * 4294967296 / 86400 as hashrate
        FROM shares
        WHERE ts > now() - INTERVAL 24 HOUR
        {where_clause}
        GROUP BY miner, worker
    ),
    worker_status AS (
        SELECT 
            miner, worker,
            last_share_ts,
            state
        FROM worker_state
        {where_clause_standalone}
    )
    SELECT 
        w.miner, 
        w.worker,
        toUnixTimestamp(w.last_share_ts) as last_share_ts,
        w.state,
        ifNull(s5.shares, 0) as shares_5m,
        ifNull(s5.hashrate, 0) as hashrate_5m,
        ifNull(s5.share_value, 0) as share_value_5m,
        ifNull(s60.shares, 0) as shares_60m,
        ifNull(s60.hashrate, 0) as hashrate_60m,
        ifNull(s60.share_value, 0) as share_value_60m,
        ifNull(s24.shares, 0) as shares_24h,
        ifNull(s24.hashrate, 0) as hashrate_24h,
        ifNull(s24.share_value, 0) as share_value_24h
    FROM worker_status w
    LEFT JOIN stats_5m s5 ON (w.miner = s5.miner AND w.worker = s5.worker)
    LEFT JOIN stats_60m s60 ON (w.miner = s60.miner AND w.worker = s60.worker)
    LEFT JOIN stats_24h s24 ON (w.miner = s24.miner AND w.worker = s24.worker)
    ORDER BY w.miner, w.worker
    """

    result = await db.client.query(query, parameters=params)

    workers = []
    for row in result.result_rows:
        workers.append(
            {
                "miner": row[0],
                "worker": row[1],
                "last_share_ts": row[2],
                "state": row[3],
                "shares_5m": row[4],
                "hashrate_5m": row[5],
                "share_value_5m": row[6],
                "shares_60m": row[7],
                "hashrate_60m": row[8],
                "share_value_60m": row[9],
                "shares_24h": row[10],
                "hashrate_24h": row[11],
                "share_value_24h": row[12],
            }
        )

    return workers
