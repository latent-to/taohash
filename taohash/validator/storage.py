from typing import Optional, Union

from bittensor.core.config import Config
from bittensor.utils.btlogging import logging

from taohash.core.storage import BaseJsonStorage, BaseRedisStorage


class JsonValidatorStorage(BaseJsonStorage):
    def __init__(self, config: Optional["Config"] = None):
        super().__init__(config)
        self.validator_id = self.generate_user_id(config)

    def save_state(self, state: dict) -> None:
        """Save the validator state to a single JSON file."""
        prefix = f"{self.validator_id}_state"
        self.save_data(key="current", data=state, prefix=prefix)
        logging.debug(f"Saved validator state at block {state['current_block']}")

    def load_latest_state(self) -> dict:
        """Load the latest saved validator state."""
        prefix = f"{self.validator_id}_state"
        return self.load_data(key="current", prefix=prefix)


class RedisValidatorStorage(BaseRedisStorage):
    def __init__(self, config: Optional["Config"] = None):
        super().__init__(config)
        self.validator_id = self.generate_user_id(config)

    def save_state(self, state: dict) -> None:
        """Save the validator state to a single JSON file."""
        prefix = f"{self.validator_id}_state"
        self.save_data(key="current", data=state, prefix=prefix)

    def load_latest_state(self) -> dict:
        """Get validator state for specific block."""
        prefix = f"{self.validator_id}_state"
        return self.load_data(key="current", prefix=prefix)


STORAGE_CLASSES = {"json": JsonValidatorStorage, "redis": RedisValidatorStorage}


# Factory function to get storage
def get_validator_storage(
    storage_type: str, config: "Config"
) -> Union["JsonValidatorStorage", "RedisValidatorStorage"]:
    """Get a Validator storage instance based on a passed storage type.

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
