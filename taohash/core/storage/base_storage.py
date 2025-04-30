import uuid
from abc import ABC, abstractmethod
from argparse import ArgumentParser
from typing import Any, Optional

import bittensor


class BaseStorage(ABC):
    @classmethod
    @abstractmethod
    def add_args(cls, parser: "ArgumentParser"):
        """Add storage-specific arguments to the parser."""
        pass

    @abstractmethod
    def save_data(self, key: Any, data: Any, prefix: Optional[Any]) -> None:
        """Saves data by key."""
        pass

    @abstractmethod
    def load_data(self, key: Any, prefix: Optional[Any]) -> Any:
        """Loads data by key. Returns None if the key is not found."""
        pass

    @abstractmethod
    def get_latest(self, prefix: Optional[Any]) -> Any:
        """Returns the key of the last saved element based on the prefix."""
        pass

    def get_config(self):
        """Returns the config object for specific storage based on class implementation."""
        parser = ArgumentParser()
        self.add_args(parser)
        return bittensor.config(parser)

    @staticmethod
    def generate_user_id(config: "bittensor.config") -> str:
        """
        Generate a unique prefix for storage based on the neuron's identity.

        Args:
            config: Bittensor config containing wallet and network info

        Returns:
            str: A unique prefix string for this neuron based on wallet name, netuid, and a random UUID.
        """
        wallet_hotkey = getattr(config.wallet, "hotkey", "hk_unknown")
        netuid = getattr(config, "netuid", "netuid_unknown")
        return f"{wallet_hotkey}_{netuid}_{uuid.uuid4().hex}".upper()
