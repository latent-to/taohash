from abc import ABC, abstractmethod
from argparse import ArgumentParser
from typing import Any, Optional

import bittensor


class BaseStorage(ABC):
    @classmethod
    @abstractmethod
    def add_args(cls, parser: "ArgumentParser"):
        """Add storage-specific arguments to parser."""
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
        """Returns the key of the last saved element based on prefix."""
        pass

    def get_config(self):
        """Returns the config object for specific storage based on class implementation."""
        parser = ArgumentParser()
        self.add_args(parser)
        return bittensor.config(parser)

    def generate_user_id(self, config: "bittensor.config") -> str:
        """
        Generate a unique prefix for storage based on neuron's identity.

        Args:
            config: Bittensor config containing wallet and network info

        Returns:
            str: A unique prefix string for this neuron
        """
        network = getattr(config.subtensor, "network", "unknown")
        wallet_name = getattr(config.wallet, "name", "unknown")
        wallet_hotkey = getattr(config.wallet, "hotkey", "unknown")
        netuid = getattr(config, "netuid", "unknown")

        return f"{network}_{netuid}_{wallet_name}_{wallet_hotkey}"
