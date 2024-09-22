from typing import Dict, Optional

import abc
from enum import Enum

import argparse

from api import PoolAPI
from braiins import BraiinsPool


class PoolEnum(Enum):
    Braiins = "braiins"


class Pool(metaclass=abc.ABCMeta):
    api_key: str
    api: PoolAPI

    def __init__(self, api_key: str, api: PoolAPI) -> None:
        self.api_key = api_key
        self.api = api

    def __new__(cls, pool: PoolEnum, api_key: str) -> "Pool":
        pool_ = __ENUM_MAP[pool]
        api = pool_.create_api(api_key)

        return pool_(api_key, api)

    @staticmethod
    def _get_worker_id_for_hotkey(hotkey: str) -> str:
        return hotkey

    @abc.abstractmethod
    def get_hashrate_for_hotkey(self, hotkey: str, coin: str) -> float:
        return

    @classmethod
    @abc.abstractmethod
    def create_api(cls, api_key: str) -> PoolAPI:
        pass

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser", prefix: Optional[str] = None):
        parser.add_argument("--pool.pool", type=PoolEnum, choices=list(PoolEnum))
        parser.add_argument("--pool.api_key", required=True, type=str)


__ENUM_MAP: Dict[PoolEnum, Pool] = {PoolEnum.Braiins: BraiinsPool}
