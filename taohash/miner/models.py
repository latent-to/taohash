from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:   
    from taohash.chain_data.chain_data import PoolInfo

@dataclass
class MiningSlot:
    start_block: int
    end_block: int
    total_blocks: int
    validator_hotkey: str
    pool_info: "PoolInfo"

    def __eq__(self, other):
        if not isinstance(other, MiningSlot):
            return False
        return (
            self.start_block == other.start_block
            and self.end_block == other.end_block
            and self.validator_hotkey == other.validator_hotkey
        )

@dataclass
class MiningSchedule:
    slots: list["MiningSlot"]
    total_blocks: int
    created_at_block: int
    end_block: int

    def __init__(self, slots: list["MiningSlot"], total_blocks: int, created_at_block: int):
        self.slots = slots
        self.total_blocks = total_blocks
        self.created_at_block = created_at_block
        self.end_block = created_at_block + total_blocks - 1

    def get_slot_for_block(self, block: int) -> Optional["MiningSlot"]:
        """Get the slot for a given block number."""
        return next(
            (slot for slot in self.slots 
             if slot.start_block <= block <= slot.end_block),
            None
        )
