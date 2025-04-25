from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from taohash.core.chain_data.pool_info import PoolInfo


@dataclass
class MiningSlot:
    """
    Represents a time period (in blocks) allocated to one or more validator pools.
    
    Each slot defines a specific range of blocks and which validator pools should 
    receive hashrate during that period, including proportional distribution if 
    multiple pools are targeted simultaneously.

    Attributes:
        start_block: First block in this slot's range
        end_block: Last block in this slot's range
        total_blocks: Number of blocks in this slot
        pool_targets: List of validator target pools proportions
    """
    start_block: int
    end_block: int
    total_blocks: int
    pool_targets: list["PoolTarget"]

    def __eq__(self, other):
        """
        Check if two MiningSlot objects are equal.
        
        Args:
            other: The object to compare against
            
        Returns:
            bool: True if the slots are equal, False otherwise
        """
        if not isinstance(other, MiningSlot):
            return False
        return (
            self.start_block == other.start_block
            and self.end_block == other.end_block
            and self.pool_targets == other.pool_targets
        )


@dataclass
class PoolTarget:
    """
    Defines a validator pool to direct hashrate toward, with an optional proportion.
    
    When multiple pools are targeted within a single slot, the proportion determines
    the percentage of hashrate that should be directed to each validator.

    Attributes:
        validator_hotkey: The hotkey identifying the validator
        proportion: Fraction of hashrate to direct to this validator (0.0-1.0)
        pool_info: Connection details for the validator's mining pool
    """
    validator_hotkey: str
    proportion: float
    pool_info: "PoolInfo"


@dataclass
class MiningSchedule:
    """
    A complete mining schedule composed of sequential mining slots covering a block range.
    
    Tracks the current active mining slot and provides methods to determine which validator
    pools should receive hashrate at any given block height.

    Attributes:
        slots: List of MiningSlot objects in chronological order
        total_blocks: Total number of blocks covered by this schedule
        created_at_block: Block number when this schedule was created
        end_block: Last block covered by this schedule
        current_slot: The currently active mining slot
    """
    slots: list["MiningSlot"]
    total_blocks: int
    created_at_block: int
    end_block: int
    current_slot: Optional["MiningSlot"] = None

    def __init__(
        self, slots: list["MiningSlot"], total_blocks: int, created_at_block: int
    ):
        """
        Initialize a mining schedule with slots and metadata.
        
        Args:
            slots: Sequential list of mining slots defining the schedule
            total_blocks: Total number of blocks covered by this schedule
            created_at_block: Block number when this schedule was created
        """
        self.slots = slots
        self.total_blocks = total_blocks
        self.created_at_block = created_at_block
        self.end_block = self.slots[-1].end_block if self.slots else None
        self.current_slot = None

    def get_slot_for_block(self, block: int) -> Optional["MiningSlot"]:
        """Find the mining slot that contains the specified block number."""
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
        Update the current active slot based on the given block number.
        Returns the new slot if it changed, None otherwise.
        """
        target_slot = self.get_slot_for_block(block)
        if target_slot != self.current_slot:
            self.current_slot = target_slot
            return target_slot
        return None
