import json
import os
from pathlib import Path
from typing import Optional

from bittensor.utils.btlogging import logging


class BaseValidatorStorage:
    @classmethod
    def add_args(cls, parser):
        """Add storage-specific arguments to parser."""
        pass

    def save_state(self, state: dict) -> None:
        """Save validator state."""
        pass

    def get_latest_state(self) -> Optional[dict]:
        """Get most recent validator state."""
        pass


class JsonValidatorStorage(BaseValidatorStorage):
    DEFAULT_PATH = "~/.bittensor/data/taohash/validator"
    STATE_FILENAME = "validator_state.json"

    @classmethod
    def add_args(cls, parser):
        parser.add_argument(
            "--recovery_file_path",
            type=str,
            default=os.getenv("RECOVERY_FILE_PATH", cls.DEFAULT_PATH),
            help="Path to save validator state JSON files",
        )
        parser.add_argument(
            "--recovery_file_name",
            type=str,
            default=os.getenv("RECOVERY_FILE_NAME", cls.STATE_FILENAME),
            help="Filename to save validator state JSON files",
        )

    def __init__(self, config):
        self.base_path = Path(config.recovery_file_path).expanduser()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.state_file = self.base_path / config.recovery_file_name

    def save_state(self, state: dict) -> None:
        """
        Save validator state to a single JSON file.
        """
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=4)

        logging.debug(f"Saved validator state at block {state['current_block']}")

    def get_latest_state(self) -> Optional[dict]:
        """
        Get the latest validator state.
        Returns:
            Optional[dict]: The latest validator state or None if no state exists
        """
        if not self.state_file.exists():
            return None

        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
                return state
        except (json.JSONDecodeError, OSError) as e:
            logging.error(f"Error loading state file: {e}")
            return None


# Factory function to get storage
def get_validator_storage(config) -> JsonValidatorStorage:
    """Get validator storage instance."""
    try:
        return JsonValidatorStorage(config)
    except Exception as e:
        logging.error(f"Failed to initialize validator storage: {e}")
        exit(1)
