import argparse
from typing import Optional, Callable

from taohash.core.chain_data.pool_info import PoolInfo
from taohash.core.pool.braiins import BraiinsPool
from taohash.core.pool.proxy import ProxyPool
from taohash.core.pool.config import PoolAPIConfig
from taohash.core.pool.pool import PoolBase, PoolIndex

POOL_URLS_FMT: dict[PoolIndex, Callable[[PoolInfo], str]] = {
    PoolIndex.Braiins: lambda pool_info: f"stratum+tcp://{pool_info.domain}:{pool_info.port}",
    PoolIndex.Custom: lambda pool_info: f"stratum+tcp://{pool_info.ip}:{pool_info.port}",
    PoolIndex.Proxy: lambda pool_info: f"http://{pool_info.ip}:{pool_info.port}",
}


class Pool:
    """
    Factory class for creating mining pool instances.

    Creates the appropriate pool implementation based on the pool_info.pool_index
    and initializes it with the provided API configuration.
    """

    __CLASS_MAP: dict[int, PoolBase] = {
        PoolIndex.Braiins: BraiinsPool,
        PoolIndex.Proxy: ProxyPool,
    }

    def __new__(cls, pool_info: PoolInfo, config: PoolAPIConfig) -> "PoolBase":
        """
        Create a new pool instance based on the specified pool info.

        Args:
            pool_info: Pool information including connection details
            config: API configuration for accessing pool data

        Returns:
            An instance of the appropriate pool implementation
        """
        pool_ = cls.__CLASS_MAP[pool_info.pool_index]
        api = pool_.create_api(config)

        return pool_(pool_info, api)

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser", _: Optional[str] = None):
        # parser.add_argument("--pool.pool", type=PoolEnum, choices=list(PoolEnum))
        # parser.add_argument("--pool.api_key", required=True, type=str)
        pass
