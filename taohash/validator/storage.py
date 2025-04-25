from typing import Optional, Union

from bittensor.core.config import Config
from bittensor.utils.btlogging import logging

from taohash.core.storage import BaseJsonStorage, BaseRedisStorage


class JsonValidatorStorage(BaseJsonStorage):

    def __init__(self, config: Optional["Config"] = None):
        super().__init__(config)

    def save_state(self, block_number: int, state: dict) -> None:
        """Save validator state to a single JSON file."""
        self.save_data(key=block_number, data=state, prefix="state")
        logging.debug(f"Saved validator state at block {state['current_block']}")

    def get_state(self, block_number: int) -> dict:
        """Get validator state for specific block."""
        return self.load_data(key=block_number, prefix="state")

    def load_latest_state(self) -> dict:
        """Load the latest saved validator state."""
        return self.get_latest(prefix="state")


class RedisValidatorStorage(BaseRedisStorage):
    def __init__(self, config: Optional["Config"] = None):
        super().__init__(config)

    def save_state(self, state: dict) -> None:
        """Save validator state to a single JSON file."""
        key = state.get("current_block")
        self.save_data(key=key, data=state, prefix="state")

    def get_state(self, block_number: int) -> dict:
        """Get validator state for specific block."""
        return self.load_data(key=block_number, prefix="state")

    def load_latest_state(self) -> dict:
        """Load the latest saved validator state."""
        return self.get_latest(prefix="state")


STORAGE_CLASSES = {"json": JsonValidatorStorage, "redis": RedisValidatorStorage}


# Factory function to get storage
def get_validator_storage(storage_type: str, config: "Config") -> Union["JsonValidatorStorage", "RedisValidatorStorage"]:
    """Get validator storage instance."""
    if storage_type not in STORAGE_CLASSES:
        raise ValueError(f"Unknown storage type: {storage_type}")

    storage_class = STORAGE_CLASSES[storage_type]

    try:
        return storage_class(config)
    except Exception as e:
        message = f"Failed to initialize {storage_type} storage: {e}"
        logging.error(message)
        raise Exception(message)
