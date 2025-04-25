from abc import ABC, abstractmethod
from argparse import ArgumentParser
from typing import Any


class BaseStorage(ABC):

    @classmethod
    @abstractmethod
    def add_args(cls, parser: "ArgumentParser"):
        """Add storage-specific arguments to parser."""
        pass

    @abstractmethod
    def save_data(self, key: int, data: Any) -> None:
        """Saves data by key."""
        pass

    @abstractmethod
    def load_data(self, key: int) -> Any:
        """Loads data by key. Returns None if the key is not found."""
        pass

    @abstractmethod
    def get_latest(self) -> Any:
        """Returns the key of the last saved element (if needed)."""
        pass
