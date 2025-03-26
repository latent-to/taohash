from typing import Dict, Optional, Callable

import argparse
import bittensor

from .pool import PoolBase, PoolEnum, PoolIndex
from .braiins import BraiinsPool

__CLASS_MAP: Dict[PoolEnum, PoolBase] = {PoolEnum.Braiins: BraiinsPool}

POOL_URLS_FMT: Dict[PoolIndex, Callable[[bittensor.AxonInfo], str]] = {
    PoolIndex.Braiins: lambda _: "stratum+tcp://stratum.braiins.com:3333",
    PoolIndex.Custom: lambda axon: f"stratum+tcp://{axon.ip}:{axon.port}",
}


class Pool:
    def __new__(cls, pool: PoolEnum, api_key: str) -> "PoolBase":
        pool_ = __CLASS_MAP[pool]
        api = pool_.create_api(api_key)

        return pool_(api_key, api)

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser", _: Optional[str] = None):
        parser.add_argument("--pool.pool", type=PoolEnum, choices=list(PoolEnum))
        parser.add_argument("--pool.api_key", required=True, type=str)
