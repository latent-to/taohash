import json
import os

from pathlib import Path
from argparse import ArgumentParser
from typing import Optional


from taohash.core.storage import BaseStorage


class JsonStorage(BaseStorage):

    DEFAULT_PATH = os.path.join("~", ".bittensor", "data", "pools")

    def __init__(self, config):
        self.base_path = Path(config.json_path).expanduser()
        self.base_path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def add_args(cls, parser: "ArgumentParser"):
        """Add storage-specific arguments to parser."""
        parser.add_argument(
            "--json_path",
            type=str,
            default=os.getenv("JSON_PATH", cls.DEFAULT_PATH),
            help="Path to save pool configuration JSON files",
        )

    def save_data(self, block_number: int, pool_mapping: dict) -> None:
        """Save json file for specific block."""
        pool_data_file = self.base_path / f"{block_number}-pools.json"
        with open(pool_data_file, "w") as f:
            json.dump(pool_mapping, f, indent=4)

    def load_data(self, block_number: int) -> Optional[dict]:
        """Get json file for specific block."""
        pool_file = self.base_path / f"{block_number}-pools.json"
        if not pool_file.exists():
            return None
        with open(pool_file) as f:
            return json.load(f)

    def get_latest(self) -> Optional[dict]:
        """Get most recent json file."""
        files = list(self.base_path.glob("*-pools.json"))
        if not files:
            return None

        latest_file = max(files, key=lambda f: int(f.stem.split("-")[0]))
        with open(latest_file) as f:
            return json.load(f)
