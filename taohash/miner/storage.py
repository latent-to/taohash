import json
import base64

from typing import Optional, Union

from bittensor.core.config import Config
from bittensor.utils.btlogging import logging

from taohash.core.storage import BaseJsonStorage, BaseRedisStorage
from taohash.core.storage.utils import dumps, loads


class JsonStorage(BaseJsonStorage):
    def __init__(self, config: Optional["Config"] = None):
        super().__init__(config)
        self.miner_id = self.generate_user_id(config)

    def save_pool_data(self, block_number: int, pool_mapping: dict) -> None:
        """Save pool data for specific block."""
        prefix = f"{self.miner_id}_pools"
        # Do cleanup check each time before saving new json data
        self._cleanup()
        self.save_data(key=block_number, data=pool_mapping, prefix=prefix)

    def get_pool_info(self, block_number: int) -> Optional[dict]:
        """Get pool info for specific block."""
        prefix = f"{self.miner_id}_pools"
        return self.load_data(key=block_number, prefix=prefix)

    def get_latest_pool_info(self) -> Optional[dict]:
        """Get most recent pool info."""
        prefix = f"{self.miner_id}_pools"
        return self.get_latest(prefix=prefix)

    def save_schedule(self, block_number: int, schedule_obj) -> None:
        readable_data = json.dumps(schedule_obj, default=lambda x: x.__dict__)
        dumped_data = dumps(schedule_obj)
        string_data = base64.b64encode(dumped_data).decode("utf-8")
        dict_data = {"data": readable_data, "data_encoded": string_data}
        prefix = f"{self.miner_id}_schedule"
        self.save_data(key=block_number, data=dict_data, prefix=prefix)

    def load_latest_schedule(self):
        prefix = f"{self.miner_id}_schedule"
        data = self.get_latest(prefix=prefix)
        if data is None:
            return None
        string_data = data.get("data_encoded")
        decoded_data = base64.b64decode(string_data.encode("utf-8"))
        return loads(decoded_data)


class RedisStorage(BaseRedisStorage):
    def __init__(self, config: Optional["Config"] = None):
        super().__init__(config)
        self.miner_id = self.generate_user_id(config)

    # Pool data
    def save_pool_data(self, block_number: int, pool_mapping: dict) -> None:
        prefix = f"{self.miner_id}_pools"
        self.save_data(key=block_number, data=pool_mapping, prefix=prefix)

    def get_pool_info(self, block_number: int) -> Optional[dict]:
        prefix = f"{self.miner_id}_pools"
        return self.load_data(key=block_number, prefix=prefix)

    def get_latest_pool_info(self) -> Optional[dict]:
        prefix = f"{self.miner_id}_pools"
        return self.get_latest(prefix=prefix)

    # Schedule data
    def save_schedule(self, block_number: int, schedule_obj) -> None:
        prefix = f"{self.miner_id}_schedule"
        self.save_data(key=block_number, data=schedule_obj, prefix=prefix)

    def load_latest_schedule(self):
        prefix = f"{self.miner_id}_schedule"
        return self.get_latest(prefix=prefix)


STORAGE_CLASSES = {"json": JsonStorage, "redis": RedisStorage}


def get_miner_storage(
    storage_type: str, config: "Config"
) -> Union[JsonStorage, RedisStorage]:
    """Get storage instance based on type."""
    if storage_type not in STORAGE_CLASSES:
        raise ValueError(f"Unknown storage type: {storage_type}")

    storage_class = STORAGE_CLASSES[storage_type]

    try:
        return storage_class(config)
    except Exception as e:
        message = f"Failed to initialize {storage_type} storage: {e}"
        logging.error(message)
        raise Exception(message)
