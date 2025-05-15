from typing import Union
from bittensor.core.config import Config
from bittensor.utils.btlogging import logging

from taohash.miner.proxy.braiins_farm.controller import BraiinsProxyManager
from taohash.miner.proxy.taohash_proxy.controller import TaohashProxyManager
from taohash.miner.proxy.base import BaseProxyManager

__all__ = ["BaseProxyManager", "BraiinsProxyManager", "TaohashProxyManager"]

PROXY_CLASSES = {
    "taohash": TaohashProxyManager,
    "braiins": BraiinsProxyManager,
}


def get_proxy_manager(
    proxy_type: str, config: "Config"
) -> Union[TaohashProxyManager, BraiinsProxyManager]:
    """Get a proxy manager instance based on the specified proxy type.

    Arguments:
        proxy_type: The type of proxy manager to initialize.
        config: The configuration object.

    Returns:
        Proxy manager instance created based on the specified proxy type.
    """
    if proxy_type not in PROXY_CLASSES:
        raise ValueError(f"Unknown proxy type: {proxy_type}")

    proxy_class = PROXY_CLASSES[proxy_type]

    try:
        return proxy_class(config=config)
    except Exception as e:
        message = f"Failed to initialize {proxy_type} proxy manager: {e}"
        logging.error(message)
        raise Exception(message)
