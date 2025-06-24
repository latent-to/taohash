import argparse
import os
from abc import ABC, abstractmethod
from typing import Optional, Any

import bittensor as bt


class BaseProxyManager(ABC):
    """
    Abstract base class that defines the interface for proxy management.

    This interface focuses on health checks and configuration updates,
    assuming that proxies are already installed and running by the user.
    """

    @staticmethod
    def add_args(parser: "argparse.ArgumentParser") -> None:
        """
        Add proxy-related arguments to the parser.
        This should be overridden by child classes to add specific arguments.

        Args:
            parser: The argument parser
        """
        proxy_group = parser.add_argument_group("proxy")
        proxy_group.add_argument(
            "--no-proxy",
            dest="use_proxy",
            action="store_false",
            default=os.getenv("USE_PROXY", "true").lower() == "true",
            help="Disable slot‑based mining proxy",
        )

    def __init__(self, config: "bt.Config"):
        """
        Initialize the proxy manager.

        Args:
            config: Bittensor config object
        """
        self.config = config

    @abstractmethod
    def check_health(self) -> tuple[bool, Optional[str]]:
        """
        Check if the proxy is healthy and accessible

        Returns:
            tuple[bool, Optional[str]]:
                - Health status (True if healthy)
                - Status message or error description
        """
        pass

    @abstractmethod
    def update_config(self, slot_data: Any) -> bool:
        """
        Update the proxy configuration when mining slot changes

        Args:
            slot_data: Data about the new mining slot

        Returns:
            bool: True if update was successful
        """
        pass
