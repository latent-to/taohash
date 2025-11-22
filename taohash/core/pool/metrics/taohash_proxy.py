"""
Proxy pool metrics implementation for time-based queries.
"""

from dataclasses import dataclass

from taohash.core.pool.proxy.pool import ProxyPool
from taohash.core.constants import PAYOUT_FACTOR, BLOCK_REWARDS
from .base import BaseMetrics


@dataclass
class ProxyMetrics(BaseMetrics):
    """
    Mining Metrics for Proxy pool.
    Contains data about the miner's hashrate and shares for a specific time range.
    """

    hashrate: float = 0.0
    shares: int = 0
    share_value: float = 0.0
    coin: str = "btc"

    def get_share_value_fiat(
        self, coin_price: float, coin_difficulty: float, coin: str = None
    ) -> float:
        """
        Returns the share value for this time period.
        The share value is already calculated by the pool based on actual work done.

        Args:
            coin_price: Current coin price in USD
            coin_difficulty: Current network difficulty for the coin
            coin: Coin identifier (e.g., "btc", "bch"). If None, uses self.coin

        Returns:
            float: Share value in USD
        """
        if coin is None:
            coin = self.coin

        block_reward = BLOCK_REWARDS.get(coin, 3.125)

        if self.share_value:
            return (self.share_value / coin_difficulty) * block_reward * coin_price
        return 0.0


def get_metrics_timerange(
    pool: ProxyPool,
    hotkeys: list[str],
    block_at_registration: list[int],
    start_time: int,
    end_time: int,
    coin: str = "bitcoin",
) -> dict[str, any]:
    """
    Retrieves mining metrics for all miners for a specific time range.

    Args:
        pool: The pool instance to query (must be ProxyPool)
        hotkeys: List of miner hotkeys
        block_at_registration: List of registration blocks for each hotkey
        start_time: Start time as unix timestamp
        end_time: End time as unix timestamp
        coin: The coin type (default: "bitcoin")

    Returns:
        Dict containing list of ProxyMetrics and payout factor
    """
    metrics = []
    timerange_data = pool.get_miner_contributions_timerange(start_time, end_time, coin)

    all_workers = timerange_data.get("workers", {})
    payout_factor = timerange_data.get("payout_factor", PAYOUT_FACTOR)

    hotkeys_to_workers = {}
    worker_ids_to_hotkey_idx = {}

    for i, hotkey in enumerate(hotkeys):
        worker_id = pool._get_worker_id_for_hotkey(hotkey)

        if worker_id in worker_ids_to_hotkey_idx:
            # Duplicate worker ID - choose the older registration
            other_hotkey_idx = worker_ids_to_hotkey_idx[worker_id]
            if block_at_registration[i] < block_at_registration[other_hotkey_idx]:
                # Current hotkey registered earlier, use it
                other_hotkey = hotkeys[other_hotkey_idx]
                if other_hotkey in hotkeys_to_workers:
                    del hotkeys_to_workers[other_hotkey]
                worker_ids_to_hotkey_idx[worker_id] = i
                hotkeys_to_workers[hotkey] = worker_id
        else:
            # First time seeing this worker ID
            worker_ids_to_hotkey_idx[worker_id] = i
            hotkeys_to_workers[hotkey] = worker_id

    for hotkey in hotkeys:
        worker_id = hotkeys_to_workers.get(hotkey)

        if worker_id is None:
            metrics.append(ProxyMetrics(hotkey=hotkey, coin=coin))
            continue

        worker_data = all_workers.get(worker_id, {})

        metrics.append(
            ProxyMetrics(
                hotkey=hotkey,
                hashrate=worker_data.get("hashrate", 0.0),
                shares=worker_data.get("shares", 0),
                share_value=worker_data.get("share_value", 0.0),
                hash_rate_unit=worker_data.get("hash_rate_unit", "Gh/s"),
                coin=coin,
            )
        )

    return {"metrics": metrics, "payout_factor": payout_factor}
