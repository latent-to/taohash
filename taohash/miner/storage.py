from typing import Optional

from taohash.core.storage import BaseJsonStorage, BaseRedisStorage
from bittensor.utils.btlogging import logging


class JsonStorage(BaseJsonStorage):

    def __init__(self, config):
        super().__init__(config.json_path)

    def save_pool_data(self, block_number: int, pool_mapping: dict) -> None:
        """Save pool data for specific block."""
        self.save_data(key=block_number, data=pool_mapping, prefix="pools")

    def get_pool_info(self, block_number: int) -> Optional[dict]:
        """Get pool info for specific block."""
        return self.load_data(key=block_number, prefix="pools")

    def get_latest_pool_info(self) -> Optional[dict]:
        """Get most recent pool info."""
        self.get_latest("pools")

    def save_schedule(self, block_number: int, schedule_obj) -> None:
        self.save_data(key=block_number, data=schedule_obj, prefix="schedule")

    def load_latest_schedule(self):
        return self.get_latest("schedule")


class RedisStorage(BaseRedisStorage):

    def __init__(self, config):
        super().__init__(config)

    # Pool data
    def save_pool_data(self, block_number: int, pool_mapping: dict) -> None:
        self.save_data(key=block_number, data=pool_mapping, prefix="pool")

    def get_pool_info(self, block_number: int) -> Optional[dict]:
        return self.load_data(key=block_number, prefix="pool")

    def get_latest_pool_info(self) -> Optional[dict]:
        return self.get_latest("pool")

    # Schedule data
    def save_schedule(self, block_number: int, schedule_obj) -> None:
        self.save_data(key=block_number, data=schedule_obj, prefix="schedule")

    def load_latest_schedule(self):
        return self.get_latest("schedule")


STORAGE_CLASSES = {"json": JsonStorage, "redis": RedisStorage}


def get_storage(storage_type: str, config) -> JsonStorage | RedisStorage:
    """Get storage instance based on type."""
    if storage_type not in STORAGE_CLASSES:
        raise ValueError(f"Unknown storage type: {storage_type}")

    storage_class = STORAGE_CLASSES[storage_type]
    try:
        return storage_class(config)
    except Exception as e:
        logging.error(f"Failed to initialize {storage_type} storage: {e}")
        if storage_type == "redis":
            logging.error(
                "Please install redis-py package: pip install redis. After installing, make sure to start redis server."
            )
        exit(1)
