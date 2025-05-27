import os

import clickhouse_connect

from ..utils.logger import get_logger

logger = get_logger(__name__)


class StatsDB:
    """
    Database handler for storing accepted shares.
    """

    def __init__(self):
        """Initialize with connection parameters from environment variables."""
        self.client = None
        self.host = os.environ.get("CLICKHOUSE_HOST", "clickhouse")
        self.port = int(os.environ.get("CLICKHOUSE_PORT", "8123"))
        self.username = os.environ.get("CLICKHOUSE_USER", "default")
        self.password = os.environ.get("CLICKHOUSE_PASSWORD", "taohash123")
        self.required = os.environ.get("CLICKHOUSE_REQUIRED", "false").lower() == "true"

    async def init(self):
        """Initialize connection to ClickHouse."""
        logger.info(f"Initializing ClickHouse connection to {self.host}:{self.port}")

        try:
            self.client = await clickhouse_connect.get_async_client(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                database="default",
                secure=False,
                compress=True,
            )

            result = await self.client.query("SELECT version()")
            version = result.result_rows[0][0]
            logger.info(f"Connected to ClickHouse server version: {version}")

            # Create tables
            await self._create_tables()

            return True
        except Exception as e:
            logger.error(f"Failed to connect to ClickHouse: {e}")
            if self.required:
                raise
            return False

    def _get_schema_statements(self):
        """Return schema statements as a list of SQL strings."""
        return [
            # Main shares table - simplified syntax that works
            """CREATE TABLE IF NOT EXISTS shares (
                ts DateTime DEFAULT now(),
                miner String,
                worker String,
                pool String,
                pool_difficulty Float32,
                actual_difficulty Float32,
                block_hash String,
                INDEX idx_worker (worker) TYPE bloom_filter GRANULARITY 1,
                INDEX idx_ts (ts) TYPE minmax GRANULARITY 1
            )
            ENGINE = MergeTree()
            PARTITION BY toYYYYMM(ts)
            ORDER BY (worker, ts)
            SETTINGS index_granularity = 8192""",
            # Worker stats materialized view
            """CREATE MATERIALIZED VIEW IF NOT EXISTS worker_stats_mv
            ENGINE = AggregatingMergeTree()
            PARTITION BY toYYYYMM(ts)
            ORDER BY (worker, ts)
            AS
            SELECT
                toStartOfMinute(ts) as ts,
                worker,
                miner,
                countState() as share_count,
                sumState(pool_difficulty) as total_pool_difficulty,
                sumState(actual_difficulty) as total_actual_difficulty,
                maxState(actual_difficulty) as max_difficulty
            FROM shares
            GROUP BY ts, worker, miner""",
            # Pool stats materialized view
            """CREATE MATERIALIZED VIEW IF NOT EXISTS pool_stats_mv
            ENGINE = AggregatingMergeTree()
            PARTITION BY toYYYYMM(ts)
            ORDER BY ts
            AS
            SELECT
                toStartOfMinute(ts) as ts,
                uniqState(worker) as unique_workers,
                countState() as total_shares,
                sumState(pool_difficulty) as sum_pool_difficulty,
                sumState(actual_difficulty) as sum_actual_difficulty,
                maxState(actual_difficulty) as max_actual_difficulty
            FROM shares
            GROUP BY ts""",
            # Worker stats views
            """CREATE VIEW IF NOT EXISTS worker_stats_5m AS
            SELECT
                worker,
                miner,
                countMerge(share_count) as shares,
                sumMerge(total_pool_difficulty) as pool_difficulty_sum,
                sumMerge(total_actual_difficulty) as actual_difficulty_sum,
                maxMerge(max_difficulty) as max_difficulty,
                sumMerge(total_pool_difficulty) * 4294967296 / 300 as hashrate
            FROM worker_stats_mv
            WHERE ts > now() - INTERVAL 5 MINUTE
            GROUP BY worker, miner""",
            """CREATE VIEW IF NOT EXISTS worker_stats_60m AS
            SELECT
                worker,
                miner,
                countMerge(share_count) as shares,
                sumMerge(total_pool_difficulty) as pool_difficulty_sum,
                sumMerge(total_actual_difficulty) as actual_difficulty_sum,
                maxMerge(max_difficulty) as max_difficulty,
                sumMerge(total_pool_difficulty) * 4294967296 / 3600 as hashrate
            FROM worker_stats_mv
            WHERE ts > now() - INTERVAL 60 MINUTE
            GROUP BY worker, miner""",
            """CREATE VIEW IF NOT EXISTS worker_stats_24h AS
            SELECT
                worker,
                miner,
                countMerge(share_count) as shares,
                sumMerge(total_pool_difficulty) as pool_difficulty_sum,
                sumMerge(total_actual_difficulty) as actual_difficulty_sum,
                maxMerge(max_difficulty) as max_difficulty,
                sumMerge(total_pool_difficulty) * 4294967296 / 86400 as hashrate
            FROM worker_stats_mv
            WHERE ts > now() - INTERVAL 24 HOUR
            GROUP BY worker, miner""",
            # Pool stats views
            """CREATE VIEW IF NOT EXISTS pool_stats_5m AS
            SELECT
                uniqMerge(unique_workers) as active_workers,
                countMerge(total_shares) as shares,
                sumMerge(sum_pool_difficulty) as pool_difficulty_sum,
                sumMerge(sum_actual_difficulty) as actual_difficulty_sum,
                maxMerge(max_actual_difficulty) as max_difficulty,
                sumMerge(sum_pool_difficulty) * 4294967296 / 300 as hashrate
            FROM pool_stats_mv
            WHERE ts > now() - INTERVAL 5 MINUTE""",
            """CREATE VIEW IF NOT EXISTS pool_stats_60m AS
            SELECT
                uniqMerge(unique_workers) as active_workers,
                countMerge(total_shares) as shares,
                sumMerge(sum_pool_difficulty) as pool_difficulty_sum,
                sumMerge(sum_actual_difficulty) as actual_difficulty_sum,
                maxMerge(max_actual_difficulty) as max_difficulty,
                sumMerge(sum_pool_difficulty) * 4294967296 / 3600 as hashrate
            FROM pool_stats_mv
            WHERE ts > now() - INTERVAL 60 MINUTE""",
            """CREATE VIEW IF NOT EXISTS pool_stats_24h AS
            SELECT
                uniqMerge(unique_workers) as active_workers,
                countMerge(total_shares) as shares,
                sumMerge(sum_pool_difficulty) as pool_difficulty_sum,
                sumMerge(sum_actual_difficulty) as actual_difficulty_sum,
                maxMerge(max_actual_difficulty) as max_difficulty,
                sumMerge(sum_pool_difficulty) * 4294967296 / 86400 as hashrate
            FROM pool_stats_mv
            WHERE ts > now() - INTERVAL 24 HOUR""",
            # Worker state view
            """CREATE VIEW IF NOT EXISTS worker_state AS
            SELECT
                worker,
                miner,
                max(ts) as last_share_ts,
                CASE 
                    WHEN max(ts) > now() - INTERVAL 2 HOUR THEN 'ok'
                    ELSE 'offline'
                END as state
            FROM shares
            GROUP BY worker, miner""",
        ]

    async def _create_tables(self):
        """Create all tables and views."""
        try:
            for stmt in self._get_schema_statements():
                try:
                    await self.client.command(stmt)
                except Exception as e:
                    logger.error(f"Failed to create table: {e}")
                    pass

            logger.info("Database schema created/verified")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")

    async def insert_share(
        self,
        miner: str,
        worker: str,
        pool: str,
        pool_difficulty: float,
        actual_difficulty: float,
        block_hash: str = "",
        **kwargs,
    ) -> None:
        """
        Insert a share submission with minimal data.

        Args:
            miner: Miner identifier
            worker: Worker name
            pool: Pool address
            pool_difficulty: Pool difficulty
            actual_difficulty: Actual share difficulty
            block_hash: Block hash (will be reversed before storage)
        """
        if not self.client:
            return

        try:
            block_hash_reversed = block_hash[::-1] if block_hash else ""

            data = [
                [
                    miner,
                    worker,
                    pool,
                    pool_difficulty,
                    actual_difficulty,
                    block_hash_reversed,
                ]
            ]

            await self.client.insert(
                "shares",
                data,
                column_names=[
                    "miner",
                    "worker",
                    "pool",
                    "pool_difficulty",
                    "actual_difficulty",
                    "block_hash",
                ],
            )

        except Exception as e:
            logger.error(f"Error inserting share: {e}")
            if self.required:
                raise

    async def close(self):
        """Close the database connection."""
        if self.client:
            try:
                await self.client.close()
            finally:
                self.client = None
                logger.info("ClickHouse connection closed")
