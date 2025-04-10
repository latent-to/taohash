from .api import BraiinsPoolAPI
from .config import BraiinsPoolAPIConfig
from ..pool import PoolBase, PoolIndex
from ...chain_data.chain_data import PoolInfo


class BraiinsPool(PoolBase):
    api: BraiinsPoolAPI
    index = PoolIndex.Braiins

    def __init__(self, pool_info: PoolInfo, api: BraiinsPoolAPI) -> None:
        super().__init__(pool_info, api)

    def _get_worker_id_for_hotkey(self, hotkey: str) -> str:
        return hotkey[:4] + hotkey[-4:]

    def get_shares_for_hotkey(self, hotkey: str, coin: str) -> float:
        worker_id = self._get_worker_id_for_hotkey(hotkey)

        shares = self.api.get_worker_data(worker_id, coin)
        return shares

    @classmethod
    def create_api(cls, config: BraiinsPoolAPIConfig) -> BraiinsPoolAPI:
        return BraiinsPoolAPI(config.api_key)
