import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from bittensor.utils.btlogging import logging

from taohash.core.storage.base_storage import BaseStorage
from taohash.core.storage.utils import check_key, extract_block_number

DEFAULT_PATH = Path("~", ".bittensor", "data", "pools").expanduser()
DEFAULT_JSON_TTL = 7 * 24 * 3600


def _read_json(file_path: Path) -> Optional[dict]:
    """Read JSON file and return deserialized data."""
    try:
        with file_path.open("r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        logging.error(f"Error loading/decoding [red]{file_path.as_posix()}[/red] file.")
        return None


class BaseJsonStorage(BaseStorage):

    def __init__(self, config):
        self.config = config or self.get_config()

        self.path = Path(self.config.json_path) or DEFAULT_PATH
        self.path.mkdir(parents=True, exist_ok=True)
        self.json_ttl = self.config.json_ttl or DEFAULT_JSON_TTL

        # BaseJsonStorage
        self._cleanup()

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
            "--json_ttl",
            type=int,
            default=int(os.getenv("JSON_TTL", DEFAULT_JSON_TTL)),
            help="TTL for JSON data files in seconds",
        )

    def _cleanup(self):
        """Remove JSON files older than the TTL."""
        now = time.time()
        files = self.path.glob("*.json")

        for file in files:
            try:
                stat = file.stat()
                age = now - stat.st_mtime
                if age > self.json_ttl:
                    file.unlink()
                    logging.info(f"Deleted old file: {file.as_posix()}")
            except Exception as e:
                logging.error(f"Error while trying to delete {file.as_posix()}: {str(e)}")

    def save_data(self, key: Optional[Any], data: Any, prefix: str = "pools") -> None:
        """Save pool data for specific block.

        Arguments:
            key: The key to use for the record.
            data: The data to be dumped and saved.
            prefix: The prefix to use for the record.

        Example:
            current_block = 123
            data = {"ip": "0.0.0.0", "port": 12345, "weight": 1.0}
            prefix = "pools"
            save_data(current_block, data, prefix)

            current_block = 456
            data = {"start": "100", "stop": "200"}
            prefix = "schedule"
            save_data(current_block, data, prefix)
        """
        check_key(key)

        data_file = self.path / f"{prefix}-{key}.json" if key else self.path / f"{prefix}.json"
        with open(data_file, "w") as f:
            json.dump(data, f, indent=4)

    def load_data(self, key: Optional[Any], prefix: str = "pools") -> Optional[Any]:
        """Load pool data for specific block.

        Arguments:
            key: The key to use for the record.
            prefix: The prefix to use for the record.

        Returns:
            data: The deserialized data fetched from the pool data file.

        Example:
            current_block = 123
            prefix = "pools"
            get_pool_data = load_data(current_block, prefix)

            current_block = 456
            prefix = "schedule"
            get_schedule_data = load_data(current_block, prefix)
        """
        check_key(key)

        data_file = self.path / f"{prefix}-{key}.json" if key else self.path / f"{prefix}.json"
        if data_file.exists():
            return _read_json(data_file)
        return None

    def get_latest(self, prefix: str = "pools") -> Optional[Any]:
        """Load the latest saved data file matching the given prefix.

        Arguments:
            prefix: The prefix used to filter files (e.g., 'pool', 'schedule').

        Returns:
            The deserialized JSON data from the latest matching file, or None if no files found.

        Example:
            prefix = "pools"
            get_latest_pool = self.get_latest(prefix)

            prefix = "schedule"
            get_latest_schedule = self.get_latest(prefix)
        """
        files = list(self.path.glob(f"{prefix}*.json"))
        if not files:
            return None

        try:
            latest_file = max(files, key=extract_block_number)
            return _read_json(latest_file)
        except (IndexError, ValueError):
            logging.error(f"No [red]{prefix}[/red] files found in [blue]{self.path}[/blue].")
            return None
