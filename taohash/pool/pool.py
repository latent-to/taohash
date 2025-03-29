import abc
from enum import IntEnum, Enum

from .api import PoolAPI
from .config import PoolAPIConfig

class PoolEnum(Enum):
    Braiins = "braiins"


class PoolIndex(IntEnum):
    # Invalid = 0 reserved for default value
    Custom = 1  # uses the IP and Port
    Braiins = 2

    @classmethod
    def has_value(cls, value):
        return value in cls.__members__.values()


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
    def create_api(cls, config: PoolAPIConfig) -> PoolAPI:
        pass

    @abc.abstractmethod
    def get_pool_info(self) -> bytes:
        pass