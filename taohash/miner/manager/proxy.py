from typing import TYPE_CHECKING

import bittensor as bt
from taohash.miner.manager.base import BaseSlotManager
if TYPE_CHECKING:
    from taohash.miner.proxy.base import BaseProxyManager
    from taohash.miner.models import MiningSlot

class ProxySlotManager(BaseSlotManager):
    _proxy_manager: "BaseProxyManager"

    def __init__(self, proxy_manager: "BaseProxyManager"):
        self._proxy_manager = proxy_manager

    def on_slot_change(self, slot: "MiningSlot") -> None:
        success = self._proxy_manager.update_config(slot)
        if not success:
            bt.logging.warning("Failed to update proxy configuration")
