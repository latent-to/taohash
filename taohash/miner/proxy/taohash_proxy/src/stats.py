"""
Mining statistics tracking module.

This module provides classes for tracking and calculating statistics for miners
connected to the proxy. It maintains data on shares submitted, difficulty levels,
and calculates estimated hashrates based on recent share history.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class MinerStats:
    """
    Statistics tracker for an individual miner connection.

    Stores connection details, share counts, and calculates hashrate based on
    submitted shares over time using the difficulty-adjusted share method.

    Attributes:
        ip (str): Miner's IP address
        worker_name (str): Worker name from mining.authorize
        connected_at (float): Connection timestamp
        accepted (int): Count of accepted shares
        rejected (int): Count of rejected shares
        difficulty (float): Current share difficulty (effective difficulty sent to miner)
        pool_difficulty (float): Pool's requested difficulty (may differ from miner difficulty)
        recent_shares (deque): Queue of (timestamp, difficulty) tuples for hashrate calculation
        pool_type (str): Pool type (NORMAL or HIGH_DIFF)
    """

    ip: str
    worker_name: Optional[str] = None
    connected_at: float = field(default_factory=time.time)
    accepted: int = 0
    rejected: int = 0
    difficulty: float = 1.0
    pool_difficulty: float = 1.0
    recent_shares: deque = field(default_factory=lambda: deque(maxlen=100))
    pool_type: Optional[str] = None
    pool: Optional[str] = None

    def record_share(
        self, accepted: bool, difficulty: float, pool: str, error: Optional[str] = None
    ) -> None:
        """
        Record a submitted share and its result.

        Args:
            accepted (bool): Whether the share was accepted by the pool
            difficulty (float): Difficulty level of the share
            pool (str): Name of the pool
            error (Optional[str]): Error message if the share was rejected
        """
        self.pool = pool  # Update the pool name
        if accepted:
            self.accepted += 1
            self.recent_shares.append((time.time(), difficulty))
            logger.debug(f"Accepted share from {self.ip} at difficulty {difficulty}")
        else:
            self.rejected += 1
            logger.debug(
                f"Rejected share from {self.ip} at difficulty {difficulty} with error {error}"
            )

    def update_difficulty(self, difficulty: float) -> None:
        """
        Update the miner's current difficulty level.

        Args:
            difficulty (float): New difficulty level
        """
        logger.debug(f"Updated difficulty for {self.ip} to {difficulty}")
        self.difficulty = difficulty

    def get_hashrate(self) -> float:
        """
        Calculate estimated hashrate based on recent shares.

        Uses a sliding 5-minute window with the formula:
        hashrate = (sum of difficulties * 2^32) / 300 seconds

        Returns:
            float: Estimated hashrate in hashes per second
        """
        if not self.recent_shares:
            return 0.0
        
        now = time.time()
        five_min_ago = now - 300
        
        recent = [(t, d) for t, d in self.recent_shares if t > five_min_ago]
        
        if not recent:
            return 0.0
        
        if len(recent) < 10:
            return 0.0
            
        time_span = 300.0
        total_hashes = sum(diff * (2**32) for _, diff in recent)
        
        return total_hashes / time_span


class StatsManager:
    """
    Central manager for all connected miner statistics.

    Maintains a registry of all active miners and provides methods to
    register/unregister miners and retrieve aggregated statistics.
    """

    def __init__(self):
        """Initialize an empty miners registry."""
        self.miners: dict[str, MinerStats] = {}
        logger.info("StatsManager initialized")

    def register_miner(self, peer: tuple[str, int]) -> MinerStats:
        """
        Register a new miner connection and create its statistics tracker.

        Args:
            peer: (ip, port) tuple from socket connection

        Returns:
            MinerStats: Newly created statistics object for this miner
        """
        key = f"{peer[0]}:{peer[1]}"
        stats = MinerStats(ip=peer[0])
        self.miners[key] = stats
        logger.debug(f"Registered miner: {key}")
        return stats

    def unregister_miner(self, peer: tuple[str, int]) -> None:
        """
        Remove a miner from the registry when they disconnect.

        Args:
            peer: (ip, port) tuple from socket connection
        """
        key = f"{peer[0]}:{peer[1]}"
        self.miners.pop(key, None)
        logger.debug(f"Unregistered miner: {key}")

    def get_all_stats(self) -> list[dict]:
        """
        Retrieve statistics for all connected miners.

        Returns:
            list: List of formatted miner statistics
        """
        stats: list[dict] = []
        for key, s in self.miners.items():
            stats.append(
                {
                    "miner": key,
                    "worker": s.worker_name or "",
                    "accepted": s.accepted,
                    "rejected": s.rejected,
                    "difficulty": s.difficulty,
                    "pool_difficulty": s.pool_difficulty,
                    "hashrate": s.get_hashrate(),
                    "pool_type": s.pool_type or "UNKNOWN",
                    "pool": s.pool or "",
                }
            )
        return stats
