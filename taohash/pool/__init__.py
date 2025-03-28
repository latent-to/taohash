from typing import Callable, Dict, Optional
from enum import IntEnum, Enum

import argparse
import bittensor


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
POOL_SERVERS: Dict[PoolEnum, tuple[str, int]] = {
    PoolEnum.Braiins: ("stratum.braiins.com", 3333),
}

from .pool import PoolBase
from .braiins import BraiinsPool
_CLASS_MAP: Dict[PoolEnum, PoolBase] = {PoolEnum.Braiins: BraiinsPool}


class Pool:
    def __new__(cls, pool: PoolEnum, api_key: str, config: "argparse.Namespace") -> "PoolBase":
        pool_ = _CLASS_MAP[pool]
        api = pool_.create_api(api_key, config)
        try:
            ip, port = POOL_SERVERS[pool]
        except KeyError:
            raise ValueError(f"Server details not configured for pool type: {pool}")

        return pool_(api_key, api, ip=ip, port=port)

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser", _: Optional[str] = None):
        parser.add_argument("--pool.pool", required=True, type=PoolEnum, choices=list(PoolEnum))
        parser.add_argument("--pool.api_key", required=True, type=str)
        for pool_cls in _CLASS_MAP.values():
            pool_cls.add_args(parser)
