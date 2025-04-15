from dataclasses import dataclass
from typing import Optional

import bittensor as bt
from taohash.chain_data.weights_schedule import WeightsSchedule
from taohash.miner.storage import BaseStorage


@dataclass
class MiningSlot:
    """Represents a time slot for mining to a specific validator's pool"""
    start_block: int
    end_block: int
    validator_hotkey: str
    pool_url: str
    username: str
    stake_weight: float

    def __eq__(self, other):
        if not isinstance(other, MiningSlot):
            return False
        return (
            self.start_block == other.start_block and
            self.end_block == other.end_block and
            self.validator_hotkey == other.validator_hotkey
        )


@dataclass
class MiningSchedule:
    """Complete mining schedule with ordered slots"""
    slots: list[MiningSlot]
    total_blocks: int
    created_at_block: int
    
    def get_slot_for_block(self, block: int) -> Optional[MiningSlot]:
        """Get the mining slot for a specific block"""
        for slot in self.slots:
            if slot.start_block <= block <= slot.end_block:
                return slot
        return None


class MiningScheduler:
    """
    Base class for mining schedule management.
    Handles the core scheduling logic for mining slots based on validator stakes.
    """
    
    def __init__(
        self,
        config: "bt.Config",
        subtensor: "bt.subtensor",
        metagraph: "bt.metagraph",
        worker_id: str,
        weights_schedule: "WeightsSchedule",
        min_blocks_per_validator: int = 40,
        storage: BaseStorage = None
    ):
        """Initialize the mining scheduler
        
        Args:
            config: Bittensor config object
            subtensor: Bittensor subtensor instance 
            metagraph: Network metagraph
            worker_id: Unique ID for this miner
            weights_schedule: WeightsSchedule instance for tracking evaluation windows
            min_blocks_per_validator: Minimum blocks to mine for each validator
            storage: Storage backend for persistent data
        """
        self.config = config
        self.subtensor = subtensor
        self.metagraph = metagraph
        self.worker_id = worker_id
        self.weights_schedule = weights_schedule
        self.storage = storage
        
        # Scheduling params
        self.min_blocks_per_validator = min_blocks_per_validator
        self.min_blocks_for_split = min_blocks_per_validator * 2
        
        # State mgmt
        self.current_schedule: Optional[MiningSchedule] = None
        self.current_slot: Optional[MiningSlot] = None

    def create_schedule(self, current_block: int) -> MiningSchedule:
        """
        Create a new mining schedule based on remaining blocks
        
        Rules:
        1. Minimum blocks_per_validator blocks per validator
        2. If remaining blocks < 2*min_blocks_per_validator, allocate all to top validator to avoid hashing too less
        3. Otherwise, distribute in chunks of at least min_blocks_per_validator
        
        Args:
            current_block: Current block number
            
        Returns:
            MiningSchedule: New schedule with allocated mining slots
        """
        # Timing information
        blocks_until_next = self.weights_schedule.blocks_until_next_window()
        if blocks_until_next is None:
            blocks_until_next = self.weights_schedule.tempo
            
        validators = self.storage.get_latest_pool_info()
        if not validators:
            bt.logging.warning("No validators available for scheduling")
            return MiningSchedule([], 0, current_block)
            
        validator_info = list(validators.items())
        slots: list[MiningSlot] = []
        current_start_block = current_block
        remaining_blocks = blocks_until_next
        
        # If we have less than MIN_BLOCKS_FOR_SPLIT blocks, give everything to top validator
        if remaining_blocks < self.min_blocks_for_split:
            bt.logging.info(
                f"Only {remaining_blocks} blocks remaining, allocating all to top validator"
            )
            top_validator, top_data = validator_info[0]
            slots.append(MiningSlot(
                start_block=current_start_block,
                end_block=current_start_block + remaining_blocks - 1,
                validator_hotkey=top_validator,
                pool_url=top_data['pool_info']['pool_url'],
                username=top_data['full_username'],
                stake_weight=top_data['pool_weight']
            ))
        else:
            # Calculate how many validators we can support
            # TODO: Make this configurable by miners so they can choose
            # TODO: Add a configurable blacklist of validators to avoid
            max_validators = remaining_blocks // self.min_blocks_per_validator
            
            # Get total stake for selected validators
            selected_validators = validator_info[:max_validators]
            total_weight = sum(data['pool_weight'] for _, data in selected_validators)
            
            remaining_start_block = current_start_block
            unallocated_blocks = remaining_blocks
            
            for validator_hotkey, data in selected_validators:
                # Calculate blocks for this validator based on stake weight
                validator_share = (data['pool_weight'] / total_weight) * remaining_blocks
                allocated_blocks = max(
                    int(validator_share),
                    self.min_blocks_per_validator
                )
                
                # Don't exceed remaining blocks
                allocated_blocks = min(allocated_blocks, unallocated_blocks)
                
                # If remaining blocks after this allocation would be less than minimum,
                # give all remaining blocks to current validator
                blocks_after = unallocated_blocks - allocated_blocks
                if blocks_after < self.min_blocks_per_validator:
                    allocated_blocks = unallocated_blocks
                
                slots.append(MiningSlot(
                    start_block=remaining_start_block,
                    end_block=remaining_start_block + allocated_blocks - 1,
                    validator_hotkey=validator_hotkey,
                    pool_url=data['pool_info']['pool_url'],
                    username=data['full_username'],
                    stake_weight=data['pool_weight']
                ))
                
                remaining_start_block += allocated_blocks
                unallocated_blocks -= allocated_blocks
                
                # If we've allocated all blocks or can't fit another validator, stop
                if unallocated_blocks < self.min_blocks_per_validator:
                    # If we still have blocks, add them to the last validator
                    if unallocated_blocks > 0:
                        slots[-1].end_block += unallocated_blocks
                    break
        
        bt.logging.info("Created mining schedule:")
        for slot in slots:
            blocks_in_slot = slot.end_block - slot.start_block + 1
            bt.logging.info(
                f"Validator {slot.validator_hotkey[:8]}: "
                f"Blocks {slot.start_block}-{slot.end_block} "
                f"({blocks_in_slot} blocks) "
                f"Stake weight: {slot.stake_weight:.4f}"
            )
        
        return MiningSchedule(
            slots=slots,
            total_blocks=blocks_until_next,
            created_at_block=current_block
        )

    def check_and_update_schedule(
        self, 
        current_block: int
    ) -> Optional[MiningSlot]:
        """
        Check if schedule needs updating and update if needed. Uses storage to get latest pool info.
        
        Args:
            current_block: Current block number
            
        Returns:
            Optional[MiningSlot]: New slot if changed, None if no change
        """
        new_slot = None
        
        if self.current_schedule is None:
            self.current_schedule = self.create_schedule(current_block)
            new_slot = self.current_schedule.get_slot_for_block(current_block)
            
        # Check if we need a new schedule
        # Eg: 1361 >= 1000 + 360
        elif current_block >= self.current_schedule.created_at_block + self.current_schedule.total_blocks:
            self.current_schedule = self.create_schedule(current_block)
            new_slot = self.current_schedule.get_slot_for_block(current_block)
            
        # Check if we need to switch to next slot
        else:
            potential_slot = self.current_schedule.get_slot_for_block(current_block)
            if potential_slot and potential_slot != self.current_slot:
                new_slot = potential_slot

        if new_slot:
            self.current_slot = new_slot
            self._on_slot_change(new_slot)
            
        return new_slot

    def _on_slot_change(self, new_slot: MiningSlot) -> None:
        """
        Hook method called when slot changes.
        To be implemented by proxy-specific subclasses.
        
        Args:
            new_slot: The new mining slot that is being switched to
        """
        pass
