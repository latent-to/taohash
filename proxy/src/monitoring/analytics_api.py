"""
Mining analytics API for advanced share analysis and performance metrics.

Provides RESTful endpoints for analyzing mining performance, including:
- Share submission history with filtering by worker, time range, and difficulty
- Pool-wide statistics including total hashrate and active worker count
- Top worker leaderboards ranked by hashrate and share difficulty
- Aggregated metrics for evaluating mining efficiency and luck

All endpoints return JSON data suitable for charting and analysis tools.
"""

from typing import Optional
from aiohttp import web

from ..storage.db import StatsDB
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Maximum number of shares to return per query
PAGE_SIZE = 100


async def handle_analytics_page(request: web.Request) -> web.Response:
    """
    Serve the mining analytics dashboard HTML page.
    
    Returns the web interface for visualizing mining performance,
    including charts for hashrate trends, share difficulty distribution,
    and worker comparisons.
    """
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(base_dir)
    project_root = os.path.dirname(src_dir)
    analytics_path = os.path.join(project_root, "static", "analytics.html")
    return web.FileResponse(analytics_path)


async def handle_pool_stats(request: web.Request) -> web.Response:
    """
    Get aggregated mining pool statistics for the last 24 hours.
    
    Returns pool metrics including:
    - active_workers: Number of unique workers that submitted shares
    - total_shares: Total share count across all workers
    - hashrate_24h: Estimated pool hashrate in H/s based on share difficulty
    - best_share: Highest difficulty share found (potential block candidate)
    
    The hashrate calculation uses: sum(difficulty * 2^32) / time_period
    """
    db = request.app.get("stats_db")
    if not db or not db.client:
        return web.json_response({"error": "Database unavailable"}, status=503)
    
    try:
        # Get 24h pool stats
        query = """
        SELECT 
            count(DISTINCT worker) as active_workers,
            count() as total_shares,
            sum(pool_difficulty * 4294967296) / 86400 as hashrate_24h,
            max(actual_difficulty) as best_share
        FROM shares
        WHERE ts > now() - INTERVAL 24 HOUR
        """
        
        result = await db.client.query(query)
        
        if result.result_rows and result.result_rows[0]:
            row = result.result_rows[0]
            return web.json_response({
                "active_workers": int(row[0] or 0),
                "total_shares": int(row[1] or 0),
                "hashrate_24h": float(row[2] or 0),
                "best_share": float(row[3] or 0)
            })
    
    except Exception as e:
        logger.error(f"Error getting pool stats: {e}")
        return web.json_response({"error": str(e)}, status=500)
    
    return web.json_response({
        "active_workers": 0,
        "total_shares": 0,
        "hashrate_24h": 0,
        "best_share": 0
    })


async def handle_top_workers(request: web.Request) -> web.Response:
    """Get top workers for the last 24 hours."""
    db = request.app.get("stats_db")
    if not db or not db.client:
        return web.json_response({"error": "Database unavailable"}, status=503)
    
    try:
        query = """
        SELECT 
            worker,
            count() as total_shares,
            sum(accepted) as accepted_shares,
            sum(pool_difficulty * 4294967296) / 86400 as hashrate,
            max(actual_difficulty) as best_share,
            avg(actual_difficulty / pool_difficulty) as avg_luck,
            sum(accepted) / count() as accept_rate
        FROM shares
        WHERE ts > now() - INTERVAL 24 HOUR
        GROUP BY worker
        ORDER BY hashrate DESC
        LIMIT 20
        """
        
        result = await db.client.query(query)
        
        workers = []
        for row in result.result_rows:
            workers.append({
                "worker": row[0],
                "total_shares": int(row[1]),
                "accepted_shares": int(row[2]),
                "hashrate": float(row[3] or 0),
                "best_share": float(row[4] or 0),
                "avg_luck": float(row[5] or 1),
                "accept_rate": float(row[6] or 0)
            })
        
        return web.json_response(workers)
    
    except Exception as e:
        logger.error(f"Error getting top workers: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def handle_share_query(request: web.Request) -> web.Response:
    """Query share history with filters."""
    db = request.app.get("stats_db")
    if not db or not db.client:
        return web.json_response({"error": "Database unavailable"}, status=503)
    
    params = {}
    where_clauses = []
    
    worker = request.rel_url.query.get("worker")
    if worker:
        where_clauses.append("worker = %(worker)s")
        params["worker"] = worker
    
    time_range = request.rel_url.query.get("time_range", "24h")
    if time_range != "custom":
        time_map = {
            "1h": "1 HOUR",
            "6h": "6 HOUR", 
            "24h": "24 HOUR",
            "7d": "7 DAY"
        }
        where_clauses.append(f"ts > now() - INTERVAL {time_map.get(time_range, '24 HOUR')}")
    else:
        start_time = request.rel_url.query.get("start_time")
        end_time = request.rel_url.query.get("end_time")
        if start_time and end_time:
            where_clauses.append("ts >= %(start_time)s AND ts <= %(end_time)s")
            params["start_time"] = start_time
            params["end_time"] = end_time
    
    min_diff = request.rel_url.query.get("min_difficulty")
    if min_diff:
        where_clauses.append("actual_difficulty >= %(min_diff)s")
        params["min_diff"] = float(min_diff)
    
    accepted = request.rel_url.query.get("accepted")
    if accepted == "1":
        where_clauses.append("accepted = 1")
    elif accepted == "0":
        where_clauses.append("accepted = 0")
    
    limit = min(int(request.rel_url.query.get("limit", PAGE_SIZE)), 1000)
    offset = int(request.rel_url.query.get("offset", 0))
    
    where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    try:
        count_query = f"SELECT count() FROM shares WHERE {where_clause}"
        count_result = await db.client.query(count_query, parameters=params)
        total_count = int(count_result.result_rows[0][0]) if count_result.result_rows else 0
        
        query = f"""
        SELECT 
            ts,
            worker,
            pool_difficulty,
            actual_difficulty,
            accepted,
            reject_reason,
            job_id,
            block_hash
        FROM shares
        WHERE {where_clause}
        ORDER BY ts DESC
        LIMIT %(limit)s
        OFFSET %(offset)s
        """
        
        params["limit"] = limit
        params["offset"] = offset
        
        result = await db.client.query(query, parameters=params)
        
        shares = []
        for row in result.result_rows:
            shares.append({
                "ts": row[0].isoformat() if row[0] else "",
                "worker": row[1],
                "pool_difficulty": float(row[2]),
                "actual_difficulty": float(row[3]),
                "accepted": bool(row[4]),
                "reject_reason": row[5] or "",
                "job_id": row[6],
                "block_hash": row[7]
            })
        
        agg_query = f"""
        SELECT 
            avg(actual_difficulty),
            sum(actual_difficulty)
        FROM shares
        WHERE {where_clause}
        """
        
        agg_result = await db.client.query(agg_query, parameters=params)
        avg_diff = float(agg_result.result_rows[0][0] or 0) if agg_result.result_rows else 0
        total_value = float(agg_result.result_rows[0][1] or 0) if agg_result.result_rows else 0
        
        return web.json_response({
            "shares": shares,
            "total_count": total_count,
            "avg_difficulty": avg_diff,
            "total_share_value": total_value
        })
    
    except Exception as e:
        logger.error(f"Error querying shares: {e}")
        return web.json_response({"error": str(e)}, status=500)


def create_analytics_routes(app: web.Application, stats_db: Optional[StatsDB]) -> None:
    """Add analytics routes to the dashboard app."""
    app["stats_db"] = stats_db
    
    app.router.add_get("/analytics", handle_analytics_page)
    app.router.add_get("/analytics/pool-stats", handle_pool_stats)
    app.router.add_get("/analytics/top-workers", handle_top_workers)
    app.router.add_get("/analytics/shares", handle_share_query)