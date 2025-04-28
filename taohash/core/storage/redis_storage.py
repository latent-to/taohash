import argparse
import os
from typing import cast, Any, Optional

import redis

from taohash.core.storage.base_storage import BaseStorage
from taohash.core.storage.utils import check_key, dumps, loads

REDIS_DEFAULT_HOST = "localhost"
REDIS_DEFAULT_PORT = 6379
REDIS_DEFAULT_TTL = 7200
REDIS_DEFAULT_DB = 0


class BaseRedisStorage(BaseStorage):
    def __init__(self, config=None):
        self.config = config or self.get_config()
        self._port = config.redis_port or REDIS_DEFAULT_PORT
        self._host = config.redis_host or REDIS_DEFAULT_HOST
        self._db = config.redis_db or REDIS_DEFAULT_DB

        self.client = redis.Redis(host=self._host, port=self._port, db=self._db)

        self.ttl = config.redis_ttl or REDIS_DEFAULT_TTL
        self.update_redis_client()
        self.check_health()

    def update_redis_client(self):
        """Update redis client configuration."""
        self.client.config_set(name="appendonly", value="yes")

    def check_health(self):
        """Check redis connection health."""
        try:
            self.client.ping()
        except redis.exceptions.ConnectionError:
            raise ConnectionError("Redis connection error")

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
        redis_group.add_argument(
            "--redis_db",
            type=int,
            default=os.getenv("REDIS_DB", REDIS_DEFAULT_DB),
            help="Redis database",
        )

    def save_data(self, key: Optional[Any], data: Any, prefix: str = "pools") -> None:
        """
        Save data to Redis.

        Arguments:
            key: The key to use for the record.
            data: The data to be dumped and saved.
            prefix: The prefix to use for the record.

        Example:
            last_block = 123
            pool_data = {"ip": "0.0.0.0", "port": 12345, "weight": 1.0}
            prefix = "pools"
            save_data(last_block, pool_data, prefix)

            last_block = 456
            schedule_data = {"start": "100", "stop": "200"}
            prefix = "schedule"
            save_data(last_block, schedule_data, prefix)
        """
        check_key(key)

        dumped_data = dumps(data)

        pipe = self.client.pipeline()
        key_name = f"{prefix}:{key}" if key else prefix
        pipe.set(name=key_name, value=dumped_data, ex=self.ttl)
        pipe.set(name=f"{prefix}:latest_block", value=key)
        pipe.execute()

    def load_data(self, key: Optional[Any], prefix: str = "pools") -> Optional[dict]:
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
            prefix = "pools"
            get_pool_data = load_data(last_block, prefix)

            last_block = 456
            prefix = "schedule"
            get_schedule_data = load_data(last_block, prefix)

        """
        check_key(key)

        key_name = f"{prefix}:{key}" if key else prefix
        dumped_data = cast(bytes, self.client.get(name=key_name))
        data = loads(dumped_data) if dumped_data else None
        return data if data else None

    def get_latest(self, prefix: str = "pools") -> Optional[Any]:
        """Return the latest record in Redis based on prefix.

        Returns:
            latest_block_data: related with key:value as {prefix:latest_block}:latest_block_data

        Example:
            get_latest_pool = self.get_latest("pools")
            get_latest_schedule = self.get_latest("schedule")
        """
        latest_block = cast(str, self.client.get(f"{prefix}:latest_block"))
        if latest_block is None:
            return None

        data = cast(bytes, self.client.get(f"{prefix}:{int(latest_block)}"))
        return loads(data) if data else None
