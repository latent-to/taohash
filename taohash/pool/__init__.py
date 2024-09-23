from typing import Dict, Optional
from enum import IntEnum, Enum

import argparse

from .pool import PoolBase
from .braiins import BraiinsPool

class PoolEnum(Enum):
    Braiins = "braiins"

class PoolIndex(IntEnum):
    Braiins = 0


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