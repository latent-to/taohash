from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from taohash.core.chain_data.pool_info import PoolInfo


@dataclass
class MiningSlot:
    start_block: int
    end_block: int
    total_blocks: int
    pool_targets: list["PoolTarget"]

    def __eq__(self, other):
        if not isinstance(other, MiningSlot):
            return False
        return (
            self.start_block == other.start_block
            and self.end_block == other.end_block
            and self.pool_targets == other.pool_targets
        )


@dataclass
class PoolTarget:
    validator_hotkey: str
    proportion: float
    pool_info: "PoolInfo"


@dataclass
class MiningSchedule:
    slots: list["MiningSlot"]
    total_blocks: int
    created_at_block: int
    end_block: int
    current_slot: Optional["MiningSlot"] = None

    def __init__(
        self, slots: list["MiningSlot"], total_blocks: int, created_at_block: int
    ):
        self.slots = slots
        self.total_blocks = total_blocks
        self.created_at_block = created_at_block
        self.end_block = self.slots[-1].end_block if self.slots else None
        self.current_slot = None

    def get_slot_for_block(self, block: int) -> Optional["MiningSlot"]:
        """Get the slot for a given block number."""
        return next(
            (
                slot
                for slot in self.slots
                if slot.start_block <= block <= slot.end_block
            ),
            None,
        )

    def update_current_slot(self, block: int) -> Optional["MiningSlot"]:
        """
        Update the current slot based on the given block.
        Returns the new slot if it changed, None otherwise.
        """
        target_slot = self.get_slot_for_block(block)
        if target_slot != self.current_slot:
            self.current_slot = target_slot
            return target_slot
        return None
