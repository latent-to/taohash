import abc

from .api import PoolAPI

class PoolBase(metaclass=abc.ABCMeta):
    api_key: str
    api: PoolAPI

    def __init__(self, api_key: str, api: PoolAPI) -> None:
        self.api_key = api_key
        self.api = api

    @staticmethod
    def _get_worker_id_for_hotkey(hotkey: str) -> str:
        return hotkey

    @abc.abstractmethod
    def get_shares_for_hotkey(self, hotkey: str, coin: str) -> float:
        return

    def get_fpps(self, coin: str) -> float:
        return self.api.get_fpps(coin)

    @classmethod
    @abc.abstractmethod
    def create_api(cls, api_key: str) -> PoolAPI:
        pass

