import argparse
import os
import pickle
import zlib
from typing import cast, Optional, Union

import redis

from taohash.core.constants import REDIS_DEFAULT_HOST, REDIS_DEFAULT_PORT, REDIS_DEFAULT_TTL, REDIS_DEFAULT_DB
from taohash.core.storage import BaseStorage


def _dumps(obj) -> bytes:
    """pickle + light zlib compression."""
    # You can choose not to use zlib - will be easier to use data in other services
    return zlib.compress(
        pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL), level=3
    )


def _loads(blob: bytes):
    """pickle + light zlib decompression."""
    return pickle.loads(zlib.decompress(blob))


class RedisStorage(BaseStorage):
    def __init__(
        self,
        host: str = REDIS_DEFAULT_HOST,
        port: int = REDIS_DEFAULT_PORT,
        db: int = REDIS_DEFAULT_DB,
        ttl: int = REDIS_DEFAULT_TTL,
    ):
        self.client = redis.Redis(host=host, port=port, db=db)
        self.ttl = ttl

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser"):
        redis_group = parser.add_argument_group("redis storage")
        redis_group.add_argument(
            "--redis_host",
            type=str,
            default=os.getenv("REDIS_HOST", REDIS_DEFAULT_HOST),
            help="Redis host",
        )
        redis_group.add_argument(
            "--redis_port",
            type=int,
            default=os.getenv("REDIS_PORT", REDIS_DEFAULT_PORT),
            help="Redis port",
        )
        redis_group.add_argument(
            "--redis_ttl",
            type=int,
            default=os.getenv("REDIS_TTL", REDIS_DEFAULT_TTL),
            help="TTL for pool data in seconds",
        )

    def save_data(self, key: Union[str, int], data: dict, prefix: str) -> None:
        """
        Save data to Redis.

        Arguments:
            key: The key to use for the record.
            data: The data to be dumped and saved.
            prefix: The prefix to use for the record.

        Example:
            last_block = 123
            pool_data = {"ip": "0.0.0.0", "port": 12345, "weight": 1.0}
            prefix = "pool"
            save_data(last_block, pool_data, prefix)

            last_block = 456
            schedule_data = {"start": "100", "stop": "200"}
            prefix = "schedule"
            save_data(last_block, schedule_data, prefix)
        """
        key = str(key)
        data = _dumps(data)
        self.client.set(key, pickle.dumps(data))

        dumped_data = _dumps(data)
        pipe = self.client.pipeline()
        pipe.set(f"{prefix}:{key}", dumped_data, ex=self.ttl)
        pipe.set(f"{prefix}:latest_block", key)
        pipe.execute()

    def load_data(self, key: str, prefix: Optional[str]) -> Optional[dict]:
        """
        Loads and retrieves data from a client storage based on a key and optional prefix.

        Parameters:
            key (str): The key to locate the data in the client storage.
            prefix (Optional[str]): An optional prefix to prepend to the key for locating
                the data.

        Returns:
            Optional[dict]: The deserialized data fetched from the client storage, or None
                if no data exists or the deserialization fails.

        Example:
            last_block = 123
            prefix = "pool"
            get_pool_data = load_data(last_block, prefix)

            last_block = 456
            prefix = "schedule"
            get_schedule_data = load_data(last_block, prefix)

        """
        dumped_data = cast(bytes, self.client.get(f"{prefix}:{key}" if prefix else key))
        data = _loads(dumped_data) if dumped_data else None
        return data if data else None

    def get_latest(self, prefix: str) -> Optional[str]:
        """Return the latest record in Redis based on prefix.

        Returns:
            latest_block_data: related with key:value as {prefix:latest_block}:latest_block_data

        Example:
            get_latest_pool = self.get_latest("pool")
            get_latest_schedule = self.get_latest("schedule")
        """
        latest_block = cast(str, self.client.get(f"{prefix}:latest_block"))
        if latest_block is None:
            return None

        data = cast(bytes, self.client.get(f"{prefix}:{int(latest_block)}"))
        return _loads(data) if data else None
