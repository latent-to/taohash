from typing import Any

from bittensor import logging

from taohash.core.chain_data.pool_info import PoolInfo
from taohash.core.pool.config import PoolAPIConfig
from taohash.core.pool.pool import PoolBase, PoolIndex
from .api import ProxyPoolAPI
from .config import ProxyPoolAPIConfig


class ProxyPool(PoolBase):
    """
    Taohash Proxy pool implementation.

    This pool implementation connects to a Taohash proxy instance to retrieve
    miner statistics and performance data.
    """

    index = PoolIndex.Proxy
    api: ProxyPoolAPI

    def __init__(self, pool_info: PoolInfo, api: ProxyPoolAPI) -> None:
        super().__init__(pool_info, api)

    @staticmethod
    def _get_worker_id_for_hotkey(hotkey: str) -> str:
        return hotkey[:4] + hotkey[-4:]

    def get_hotkey_contribution(
        self, hotkey: str, coin: str = "bitcoin"
    ) -> dict[str, Any]:
        worker_id = self._get_worker_id_for_hotkey(hotkey)
        worker_data = self.api.get_worker_data(worker_id, coin)
        return worker_data

    def get_all_miner_contributions(
        self, coin: str = "bitcoin"
    ) -> dict[str, dict[str, Any]]:
        all_workers = self.api.get_all_workers_data(coin)
        return all_workers

    def get_miner_contributions_timerange(
        self, start_time: int, end_time: int, coin: str = "btc"
    ) -> dict[str, dict[str, Any]]:
        """
        Get mining contributions for all miners in the pool for a specific time range.

        Args:
            start_time: Start time as unix timestamp (required)
            end_time: End time as unix timestamp (required)
            coin: The coin type (default: "btc")

        Returns:
            Dictionary mapping hotkeys to their contribution metrics for the time range
        """
        all_workers = self.api.get_workers_timerange(start_time, end_time, coin)
        logging.info(
            f"Retrieved timerange data for {len(all_workers)} workers from {coin.upper()} pool"
        )
        return all_workers

    @classmethod
    def create_api(cls, config: PoolAPIConfig) -> ProxyPoolAPI:
        if not isinstance(config, ProxyPoolAPIConfig):
            raise ValueError(f"Expected ProxyPoolAPIConfig, got {type(config)}")

        return ProxyPoolAPI(
            proxy_url=config.proxy_url,
            api_token=config.api_token,
        )
