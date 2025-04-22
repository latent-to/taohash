from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from taohash.miner.models import MiningSlot

class BaseSlotManager(ABC):
    @abstractmethod
    def on_slot_change(self, slot: "MiningSlot") -> None:
        pass
