import abc
from enum import IntEnum

from taohash.core.pool.api import PoolAPI
from taohash.core.pool.config import PoolAPIConfig
from taohash.core.chain_data.pool_info import PoolInfo


class PoolIndex(IntEnum):
    """
    Enumeration of supported mining pool types.

    Used to identify and differentiate between different pool implementations
    and their connection methods.
    """

    # Invalid = 0 reserved for default value
    Custom = 1  # uses the IP and Port
    Braiins = 2

    @classmethod
    def has_value(cls, value):
        return value in cls.__members__.values()


class PoolBase(metaclass=abc.ABCMeta):
    """
    Abstract base class for mining pool implementations.

    Defines the interface for interacting with various mining pools
    and retrieving miner statistics and performance data.
    """

    api: PoolAPI
    index: PoolIndex

    def __init__(self, pool_info: PoolInfo, api: PoolAPI) -> None:
        self.pool_info = pool_info
        self.api = api

    @staticmethod
    def _get_worker_id_for_hotkey(hotkey: str) -> str:
        """
        Convert a bittensor hotkey to a mining worker ID.

        Args:
            hotkey: The hotkey string

        Returns:
            A worker ID string derived from the hotkey
        """
        return hotkey

    @abc.abstractmethod
    def get_hotkey_contribution(self, hotkey: str, coin: str) -> dict:
        """
        Get mining contribution data for a specific hotkey.

        Args:
            hotkey: The miner's hotkey
            coin: cryptocurrency being mined

        Returns:
            Dictionary containing the miner's contribution metrics
        """
        return

    @abc.abstractmethod
    def get_all_miner_contributions(self, coin: str) -> dict[str, dict]:
        """
        Get mining contributions for all miners in the pool.

        Args:
            coin: cryptocurrency being mined

        Returns:
            Dictionary mapping hotkeys to their contribution metrics
        """
        pass

    def get_fpps(self, coin: str) -> float:
        """
        Get the Full Pay Per Share (FPPS) rate for a coin.

        Args:
            coin: cryptocurrency being mined

        Returns:
            Current FPPS rate for the coin
        """
        return self.api.get_fpps(coin)

    @classmethod
    @abc.abstractmethod
    def create_api(cls, config: PoolAPIConfig) -> PoolAPI:
        """
        Create an API instance for accessing pool data.

        Args:
            config: Configuration for the pool API

        Returns:
            An initialized pool API instance
        """
        pass

    def get_pool_info(self) -> PoolInfo:
        """
        Get the pool information object.

        Returns:
            PoolInfo object containing connection details
        """
        return self.pool_info
