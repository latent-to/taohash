from .api import BraiinsPoolAPI
from ...pool import Pool, PoolIndex


class BraiinsPool(Pool):
    api: BraiinsPoolAPI
    api_key: str
    ip: int = 0
    port: int = 0
    index = PoolIndex.Braiins

    def get_shares_for_hotkey(self, hotkey: str, coin: str) -> float:
        worker_id = self._get_worker_id_for_hotkey(hotkey)
        if self.api.work_exists(worker_id):
            shares = self.api.get_shares_for_worker(worker_id, coin)
            return shares
        else:
            return 0.0  # No shares

    @classmethod
    def create_api(cls, api_key: str) -> BraiinsPoolAPI:
        return BraiinsPoolAPI(api_key)
