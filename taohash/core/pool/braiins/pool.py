from taohash.core.chain_data.pool_info import PoolInfo
from taohash.core.pool.braiins.api import BraiinsPoolAPI
from taohash.core.pool.braiins.config import BraiinsPoolAPIConfig
from taohash.core.pool.pool import PoolBase, PoolIndex


class BraiinsPool(PoolBase):
    api: BraiinsPoolAPI
    index = PoolIndex.Braiins

    def __init__(self, pool_info: PoolInfo, api: BraiinsPoolAPI) -> None:
        super().__init__(pool_info, api)

    def _get_worker_id_for_hotkey(self, hotkey: str) -> str:
        return hotkey[:4] + hotkey[-4:]

    def get_hotkey_contribution(self, hotkey: str, coin: str) -> dict[str, dict]:
        worker_id = self._get_worker_id_for_hotkey(hotkey)
        worker_data = self.api.get_worker_data(worker_id, coin)
        return worker_data

    def get_all_miner_contributions(self, coin: str) -> dict[str, dict]:
        all_workers_data = self.api.get_all_worker_data(coin)
        return all_workers_data

    @classmethod
    def create_api(cls, config: BraiinsPoolAPIConfig) -> BraiinsPoolAPI:
        return BraiinsPoolAPI(config.api_key)
