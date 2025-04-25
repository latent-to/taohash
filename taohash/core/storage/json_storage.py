import argparse
import json
import os
from pathlib import Path
from typing import Any, Optional

from taohash.core.storage.base_storage import BaseStorage
from taohash.core.storage.utils import check_key, extract_block_number

DEFAULT_PATH = Path("~", ".bittensor", "data", "pools").expanduser()
STATE_FILENAME = "state.json"


class BaseJsonStorage(BaseStorage):

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path) or DEFAULT_PATH
        self.path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser"):
        """Add Json storage-specific arguments to parser."""
        parser.add_argument(
            "--json_path",
            type=str,
            default=os.getenv("JSON_PATH", DEFAULT_PATH),
            help="Path to save pool configuration JSON files",
        )
        parser.add_argument(
            "--state_file_name",
            type=str,
            default=os.getenv("RECOVERY_FILE_NAME", STATE_FILENAME),
            help="Filename to save state JSON files.",
        )

    def save_data(self, key: Any, data: dict, prefix: str = "pools") -> None:
        """Save pool data for specific block.

        Arguments:
            key: The key to use for the record.
            data: The data to be dumped and saved.
            prefix: The prefix to use for the record.

        Example:
            current_block = 123
            data = {"ip": "0.0.0.0", "port": 12345, "weight": 1.0}
            prefix = "pool"
            save_data(current_block, data, prefix)

            current_block = 456
            data = {"start": "100", "stop": "200"}
            prefix = "schedule"
            save_data(current_block, data, prefix)
        """
        check_key(key)

        data_file = self.path / f"{prefix}-{key}.json"
        with open(data_file, "w") as f:
            json.dump(data, f, indent=4)

    def load_data(self, key: Any, prefix: str = "pool") -> Optional[dict]:
        """Load pool data for specific block.

        Arguments:
            key: The key to use for the record.
            prefix: The prefix to use for the record.

        Returns:
            data: The deserialized data fetched from the pool data file.

        Example:
            current_block = 123
            prefix = "pool"
            get_pool_data = load_data(current_block, prefix)

            current_block = 456
            prefix = "schedule"
            get_schedule_data = load_data(current_block, prefix)
        """
        check_key(key)

        data_file = self.path / f"{prefix}-{key}.json"
        if data_file.exists():
            with data_file.open("r") as f:
                return json.load(f)
        return None

    def get_latest(self, prefix: str = "pool") -> Optional[str]:
        """Load the latest saved data file matching the given prefix.

        Arguments:
            prefix: The prefix used to filter files (e.g., 'pool', 'schedule').

        Returns:
            The deserialized JSON data from the latest matching file, or None if no files found.

        Example:
            prefix = "pool"
            get_latest_pool = self.get_latest(prefix)

            prefix = "schedule"
            get_latest_schedule = self.get_latest(prefix)
        """
        files = list(self.path.glob(f"{prefix}-*.json"))
        if not files:
            return None

        try:
            latest_file = max(files, key=extract_block_number)
        except (IndexError, ValueError):
            # TODO: parsable add logging
            return None

        try:
            with latest_file.open("r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            # TODO: parsable add logging
            return None
