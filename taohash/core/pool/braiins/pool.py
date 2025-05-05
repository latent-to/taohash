from typing import Dict

from taohash.core.pool.braiins.primary_pool.api import PrimaryPoolAPI
from taohash.core.pool.braiins.api import BraiinsPoolAPI
from taohash.core.pool.braiins.config import BraiinsPoolAPIConfig
from taohash.core.pool.pool import PoolBase, PoolIndex
from taohash.core.chain_data.pool_info import PoolInfo


class BraiinsPrimaryAPIAdapter:
    def __init__(self, api: PrimaryPoolAPI, pool_name: str):
        self._api = api
        self.pool_name = pool_name

    def get_worker_data(self, worker_id: str, coin: str) -> dict:
        return self._api.get_worker_data(worker_id, self.pool_name)

    def get_all_worker_data(self, coin: str) -> dict:
        return self._api.get_all_worker_data(self.pool_name)

    def get_fpps(self, coin: str) -> float:
        return self._api.get_fpps(coin)

    def _get_worker_id_for_hotkey(self, hotkey: str) -> str:
        parts = hotkey.split(".", maxsplit=1)
        return parts[1] if len(parts) > 1 else hotkey


class BraiinsPool(PoolBase):
    api: BraiinsPoolAPI
    index = PoolIndex.Braiins

    def __init__(self, pool_info: PoolInfo, api: BraiinsPoolAPI) -> None:
        super().__init__(pool_info, api)
        if isinstance(self.api, PrimaryPoolAPI):
            self.api = BraiinsPrimaryAPIAdapter(self.api, pool_info.username)

    def _get_worker_id_for_hotkey(self, hotkey: str) -> str:
        return hotkey[:4] + hotkey[-4:]

    def get_hotkey_contribution(self, hotkey: str, coin: str) -> Dict[str, dict]:
        worker_id = self._get_worker_id_for_hotkey(hotkey)
        worker_data = self.api.get_worker_data(worker_id, coin)
        return worker_data

    def get_all_miner_contributions(self, coin: str) -> Dict[str, dict]:
        all_workers_data = self.api.get_all_worker_data(coin)
        return all_workers_data

    @classmethod
    def create_api(cls, config: BraiinsPoolAPIConfig) -> BraiinsPoolAPI:
        if config.use_primary_api:
            return PrimaryPoolAPI(config.primary_api_url, config.wallet)
        else:
            return BraiinsPoolAPI(config.api_key)
