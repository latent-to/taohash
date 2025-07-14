from typing import Optional, Union

from bittensor.core.config import Config
from bittensor.utils.btlogging import logging

from taohash.core.storage import BaseJsonStorage, BaseRedisStorage


class JsonStorage(BaseJsonStorage):
    def __init__(self, config: Optional["Config"] = None):
        super().__init__(config)
        self.miner_id = self.generate_user_id(config)

    def save_pool_data(self, block_number: int, pool_mapping: dict) -> None:
        """Save pool data for a specific block."""
        prefix = f"{self.miner_id}_pools"
        self.save_data(key=block_number, data=pool_mapping, prefix=prefix)

    def get_pool_info(self, block_number: int) -> Optional[dict]:
        """Get pool info for a specific block."""
        prefix = f"{self.miner_id}_pools"
        return self.load_data(key=block_number, prefix=prefix)

    def get_latest_pool_info(self) -> Optional[dict]:
        """Get the most recent pool info."""
        prefix = f"{self.miner_id}_pools"
        return self.get_latest(prefix=prefix)


class RedisStorage(BaseRedisStorage):
    def __init__(self, config: Optional["Config"] = None):
        super().__init__(config)
        self.miner_id = self.generate_user_id(config)

    # Pool data
    def save_pool_data(self, block_number: int, pool_mapping: dict) -> None:
        """Save pool data for a specific block.

        Arguments:
            block_number: The block number to save pool data for.
            pool_mapping: A dictionary mapping pool names to pool addresses.
        """
        prefix = f"{self.miner_id}_pools"
        self.save_data(key=block_number, data=pool_mapping, prefix=prefix)

    def get_pool_info(self, block_number: int) -> Optional[dict]:
        """Get pool info for a specific block.

        Arguments:
            block_number: The block number to get pool info for.

        Returns:
            Pool info for the specified block number, or None if not found.
        """
        prefix = f"{self.miner_id}_pools"
        return self.load_data(key=block_number, prefix=prefix)

    def get_latest_pool_info(self) -> Optional[dict]:
        """Get the most recent pool info.

        Returns:
            The latest pool info, or None if no pool info is found.
        """
        prefix = f"{self.miner_id}_pools"
        return self.get_latest(prefix=prefix)


STORAGE_CLASSES = {"json": JsonStorage, "redis": RedisStorage}


def get_miner_storage(
    storage_type: str, config: "Config"
) -> Union[JsonStorage, RedisStorage]:
    """Get a Miner storage instance based on a passed storage type.

    Arguments:
        storage_type: The type of storage to initialize.
        config: The configuration object.

    Returns:
        Storage instance created based on the specified storage type.
    """
    if storage_type not in STORAGE_CLASSES:
        raise ValueError(f"Unknown storage type: {storage_type}")

    storage_class = STORAGE_CLASSES[storage_type]

    try:
        return storage_class(config)
    except Exception as e:
        message = f"Failed to initialize {storage_type} storage: {e}"
        logging.error(message)
        raise Exception(message)
