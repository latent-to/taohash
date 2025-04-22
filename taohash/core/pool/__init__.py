from typing import Dict, Optional, Callable

import argparse

from taohash.core.pool.pool import PoolBase, PoolIndex
from taohash.core.pool.braiins import BraiinsPool
from taohash.core.pool.config import PoolAPIConfig
from taohash.core.chain_data.pool_info import PoolInfo

POOL_URLS_FMT: Dict[PoolIndex, Callable[[PoolInfo], str]] = {
    PoolIndex.Braiins: lambda pool_info: f"stratum+tcp://{pool_info.domain}:{pool_info.port}",
    PoolIndex.Custom: lambda pool_info: f"stratum+tcp://{pool_info.ip}:{pool_info.port}",
}


class Pool:
    __CLASS_MAP: Dict[int, PoolBase] = {PoolIndex.Braiins: BraiinsPool}

    def __new__(cls, pool_info: PoolInfo, config: PoolAPIConfig) -> "PoolBase":
        pool_ = cls.__CLASS_MAP[pool_info.pool_index]
        api = pool_.create_api(config)

        return pool_(pool_info, api)

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser", _: Optional[str] = None):
        # parser.add_argument("--pool.pool", type=PoolEnum, choices=list(PoolEnum))
        # parser.add_argument("--pool.api_key", required=True, type=str)
        pass
