import aiosqlite
import time
from typing import Optional


class StatsDB:
    """
    Handles storage of share events to a SQLite database.
    """

    def __init__(self, path: str):
        """
        Initialize StatsDB with path to sqlite file.
        """
        self.path = path
        self.db = None

    async def init(self):
        self.db = await aiosqlite.connect(self.path)
        await self.db.execute("PRAGMA journal_mode=WAL;")
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS share_events (
                ts         INTEGER NOT NULL,
                miner      TEXT    NOT NULL,
                pool       TEXT    NOT NULL,
                difficulty REAL    NOT NULL,
                accepted   INTEGER NOT NULL,
                error      TEXT
            );
        """)
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_share_ts
            ON share_events(ts);
        """)
        await self.db.commit()

    async def log_share(
        self,
        miner: str,
        difficulty: float,
        accepted: int,
        pool: str,
        error: Optional[str] = None,
        ts: int = None,
    ):
        """
        Record a single share event in the database.
        """
        ts = ts or int(time.time())
        await self.db.execute(
            "INSERT INTO share_events (ts, miner, pool, difficulty, accepted, error) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, miner, pool, difficulty, accepted, error),
        )
        await self.db.commit()

    async def recent_for(self, miner: str, since_ts: int):
        """
        Retrieve all share events for a given miner at or after since_ts.
        """
        cursor = await self.db.execute(
            "SELECT ts, difficulty, accepted, pool FROM share_events WHERE miner = ? AND ts >= ? ORDER BY ts ASC",
            (miner, since_ts),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return rows

    async def get_shares(self, limit: int = 100, offset: int = 0):
        """
        Retrieve share events for inspection.
        Args:
            limit: max number of rows
            offset: pagination offset
        Returns:
            List of dicts with ts, miner, pool, difficulty, accepted, error
        """
        cursor = await self.db.execute(
            "SELECT ts, miner, pool, difficulty, accepted, error"
            " FROM share_events"
            " ORDER BY ts DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        await cursor.close()

        return [
            {
                "ts": row[0],
                "miner": row[1],
                "pool": row[2],
                "difficulty": row[3],
                "accepted": bool(row[4]),
                "error": row[5],
            }
            for row in rows
        ]
