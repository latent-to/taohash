import abc
from enum import IntEnum

from taohash.core.pool.api import PoolAPI
from taohash.core.pool.config import PoolAPIConfig
from taohash.core.chain_data.pool_info import PoolInfo


class PoolIndex(IntEnum):
    # Invalid = 0 reserved for default value
    Custom = 1  # uses the IP and Port
    Braiins = 2

    @classmethod
    def has_value(cls, value):
        return value in cls.__members__.values()
# TODO: Explore config file 

class PoolBase(metaclass=abc.ABCMeta):
    api: PoolAPI
    index: PoolIndex

    def __init__(self, pool_info: PoolInfo, api: PoolAPI) -> None:
        self.pool_info = pool_info
        self.api = api

    @staticmethod
    def _get_worker_id_for_hotkey(hotkey: str) -> str:
        return hotkey

    @abc.abstractmethod
    def get_hotkey_contribution(self, hotkey: str, coin: str) -> dict:
        return

    @abc.abstractmethod
    def get_all_miner_contributions(self, coin: str) -> dict[str, dict]:
        pass

    def get_fpps(self, coin: str) -> float:
        return self.api.get_fpps(coin)

    @classmethod
    @abc.abstractmethod
    def create_api(cls, config: PoolAPIConfig) -> PoolAPI:
        pass

    def get_pool_info(self) -> PoolInfo:
        return self.pool_info
