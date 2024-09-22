from .api import BraiinsPoolAPI
from ...pool import Pool


class BraiinsPool(Pool):
    api: BraiinsPoolAPI
    api_key: str

    def get_hashrate_for_hotkey(self, hotkey: str, coin: str) -> float:
        worker_id = self._get_worker_id_for_hotkey(hotkey)
        if self.api.work_exists(worker_id):
            hashrate = self.api.get_hashrate_for_worker(worker_id, coin)
            return hashrate
        else:
            return 0.0  # No hashrate

    @classmethod
    def create_api(cls, api_key: str) -> BraiinsPoolAPI:
        return BraiinsPoolAPI(api_key)
