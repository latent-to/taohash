from typing import Callable, Dict, Optional
from enum import IntEnum, Enum

import argparse
import bittensor

from .pool import PoolBase
from .braiins import BraiinsPool


class PoolEnum(Enum):
    Braiins = "braiins"


class PoolIndex(IntEnum):
    # Invalid = 0 reserved for default value
    Custom = 1 # uses the IP and Port
    Braiins = 2

    @classmethod
    def has_value(cls, value):
        return value in cls.__members__.values()

POOL_URLS_FMT: Dict[PoolIndex, Callable[[bittensor.AxonInfo], str]] = {
    PoolIndex.Braiins: lambda _: "stratum+tcp://stratum.braiins.com:3333",
    PoolIndex.Custom: lambda axon: f"stratum+tcp://{axon.ip}:{axon.port}"
}


__CLASS_MAP: Dict[PoolEnum, PoolBase] = {PoolEnum.Braiins: BraiinsPool}


class Pool:
    def __new__(cls, pool: PoolEnum, api_key: str) -> "PoolBase":
        pool_ = __CLASS_MAP[pool]
        api = pool_.create_api(api_key)

        return pool_(api_key, api)

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser", _: Optional[str] = None):
        parser.add_argument("--pool.pool", type=PoolEnum, choices=list(PoolEnum))
        parser.add_argument("--pool.api_key", required=True, type=str)
