from abc import ABC, abstractmethod
from typing import Dict, TYPE_CHECKING
import argparse
import os

import bittensor as bt
from taohash.miner.models import MiningSlot, PoolTarget

if TYPE_CHECKING:
    from taohash.core.chain_data.pool_info import PoolInfo


class BaseAllocation(ABC):
    ALLOCATION_TYPE = "stake_based"
    MIN_BLOCKS = 40
    MAX_VALIDATORS = None
    MIN_STAKE = 12_000

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser") -> None:
        """Add common allocation arguments to parser"""
        allocation_group = parser.add_argument_group("allocation")

        allocation_group.add_argument(
            "--allocation.type",
            type=str,
            choices=["stake_based", "equal"],
            default=os.getenv("ALLOCATION_TYPE", cls.ALLOCATION_TYPE),
            help="Allocation type",
        )

        allocation_group.add_argument(
            "--allocation.min_blocks",
            type=int,
            default=os.getenv("ALLOCATION_MIN_BLOCKS", cls.MIN_BLOCKS),
            help="Minimum blocks to allocate per validator",
        )

        allocation_group.add_argument(
            "--allocation.max_validators",
            type=int,
            default=os.getenv("ALLOCATION_MAX_VALIDATORS", cls.MAX_VALIDATORS)
            or None,
            help="Maximum number of validators to include (None for all)",
        )

        allocation_group.add_argument(
            "--allocation.min_stake",
            type=float,
            default=os.getenv("ALLOCATION_MIN_STAKE", cls.MIN_STAKE),
            help="Minimum stake required for a validator to be included",
        )

    def __init__(
        self, min_blocks_per_validator=40, validator_blacklist=None, max_validators=None
    ):
        self.min_blocks_per_validator = min_blocks_per_validator
        self.min_blocks_for_split = min_blocks_per_validator * 2
        self.validator_blacklist = validator_blacklist or []
        self.max_validators = max_validators

    def create_schedule(
        self,
        current_block: int,
        available_blocks_this_window: int,
        next_window_block: int,
        pool_info: Dict[str, "PoolInfo"],
        metagraph: "bt.metagraph.Metagraph",
    ) -> list["MiningSlot"]:
        """Create mining schedule based on allocation strategy"""

        return self.allocate_slots(
            current_block,
            available_blocks_this_window,
            next_window_block,
            pool_info,
            metagraph,
        )

    def _filter_validators(
        self, pool_info: Dict[str, "PoolInfo"], metagraph: "bt.metagraph.Metagraph"
    ) -> Dict[str, "PoolInfo"]:
        """Filter and sort validators based on criteria"""
        # TODO: Min stake
        # Filter based on blacklist, metagraph, and validator permit
        filtered = {
            hotkey: info
            for hotkey, info in pool_info.items()
            if (
                hotkey not in self.validator_blacklist
                and hotkey in metagraph.hotkeys
                and metagraph.neurons[metagraph.hotkeys.index(hotkey)].validator_permit
            )
        }

        if not filtered:
            bt.logging.warning("No filtered validators found")
            return {}

        # Sort by stake
        sorted_validators = sorted(
            filtered.items(),
            key=lambda x: metagraph.neurons[
                metagraph.hotkeys.index(x[0])
            ].total_stake.tao,
            reverse=True,
        )

        # Limit number of validators if specified
        if self.max_validators:
            sorted_validators = sorted_validators[: self.max_validators]
            bt.logging.info(f"Limited targets to {self.max_validators} targets")

        return dict(sorted_validators)

    @abstractmethod
    def allocate_slots(
        self,
        current_block: int,
        available_blocks: int,
        next_window_block: int,
        pool_info: Dict[str, "PoolInfo"],
        metagraph: "bt.metagraph.Metagraph",
    ) -> list[MiningSlot]:
        """Strategy-specific slot allocation logic"""
        pass


class StakeBased(BaseAllocation):
    """Allocates blocks proportionally based on stake"""

    @staticmethod
    def add_args(parser: "argparse.ArgumentParser") -> None:
        """Add stake-based allocation specific arguments"""
        # Currently using only the base arguments, but can be extended
        # with stake-based specific arguments
        pass

    def allocate_slots(
        self,
        current_block: int,
        available_blocks: int,
        next_window_block: int,
        pool_info: Dict[str, "PoolInfo"],
        metagraph: "bt.metagraph.Metagraph",
    ) -> list[MiningSlot]:
        filtered = self._filter_validators(pool_info, metagraph)
        if not filtered:
            return []

        slots = []
        current_pos = current_block
        remaining_blocks = available_blocks

        # Calculate total stake for selected validators
        total_stake = sum(
            metagraph.neurons[metagraph.hotkeys.index(hotkey)].total_stake.tao
            for hotkey in filtered
        )

        for hotkey, pool_info in filtered.items():
            if remaining_blocks < self.min_blocks_per_validator:
                break

            stake = metagraph.neurons[metagraph.hotkeys.index(hotkey)].total_stake.tao
            fair_share = int((stake / total_stake) * available_blocks)
            bt.logging.info(
                f"\nHotkey: {hotkey} - Stake_weight: {(stake / total_stake)} ({stake:.2f} / {total_stake:.2f}). Allocated: {fair_share} / {available_blocks}"
            )

            blocks_allocated = max(
                fair_share, self.min_blocks_per_validator
            )  # Ensure min blocks are allocated
            blocks_allocated = min(
                blocks_allocated, remaining_blocks
            )  # Ensure remaining blocks are respected

            end_block = current_pos + blocks_allocated - 1

            # Ensure no overflow
            if end_block >= next_window_block:
                end_block = next_window_block - 1
                blocks_allocated = end_block - current_pos + 1
                bt.logging.debug(
                    f"Limiting slot to epoch boundary (block {next_window_block})"
                )

            # Single target with 100% proportion
            pool_target = PoolTarget(
                validator_hotkey=hotkey,
                proportion=1.0,
                pool_info=pool_info
            )

            slots.append(
                MiningSlot(
                    start_block=current_pos,
                    end_block=end_block,
                    total_blocks=blocks_allocated,
                    pool_targets=[pool_target]
                )
            )

            current_pos = end_block + 1
            remaining_blocks -= blocks_allocated

            if current_pos >= next_window_block:
                break

        # If any, add remaining to last target
        if remaining_blocks > 0 and slots and slots[-1].end_block < next_window_block:
            slots[-1].end_block = next_window_block
            slots[-1].total_blocks = slots[-1].end_block - slots[-1].start_block + 1

        return slots


# TODO: EMA Stake Based
class EMAStakeBased(BaseAllocation):
    """Allocates blocks proportionally based on EMA of stake"""


class EqualDistribution(BaseAllocation):
    """Allocates blocks equally among targets"""

    @staticmethod
    def add_args(parser: "argparse.ArgumentParser") -> None:
        """Add equal distribution specific arguments"""
        # Currently using only the base arguments, but can be extended
        # with equal distribution specific arguments
        pass

    def allocate_slots(
        self,
        current_block: int,
        available_blocks: int,
        next_window_block: int,
        pool_info: Dict[str, "PoolInfo"],
        metagraph: "bt.metagraph.Metagraph",
    ) -> list[MiningSlot]:
        filtered = self._filter_validators(pool_info, metagraph)
        if not filtered:
            return []

        slots = []
        current_pos = current_block
        remaining_blocks = available_blocks

        base_blocks = available_blocks // len(filtered)
        remainder = available_blocks % len(filtered)

        for i, (hotkey, pool_info) in enumerate(filtered.items()):
            if remaining_blocks < self.min_blocks_per_validator:
                break

            blocks_allocated = base_blocks + (1 if i < remainder else 0)
            blocks_allocated = max(
                blocks_allocated, self.min_blocks_per_validator
            )  # Ensure min blocks are allocated
            blocks_allocated = min(
                blocks_allocated, remaining_blocks
            )  # Ensure remaining blocks are respected

            end_block = current_pos + blocks_allocated - 1

            if end_block >= next_window_block:
                end_block = next_window_block - 1
                blocks_allocated = end_block - current_pos + 1
                bt.logging.debug(
                    f"Limiting slot to epoch boundary (block {next_window_block})"
                )

            # Single target with 100% proportion
            pool_target = PoolTarget(
                validator_hotkey=hotkey,
                proportion=1.0,
                pool_info=pool_info
            )

            slots.append(
                MiningSlot(
                    start_block=current_pos,
                    end_block=end_block,
                    total_blocks=blocks_allocated,
                    pool_targets=[pool_target]
                )
            )

            current_pos = end_block + 1
            remaining_blocks -= blocks_allocated

            if current_pos >= next_window_block:
                break

        # If any, add remaining to last target
        if remaining_blocks > 0 and slots and slots[-1].end_block < next_window_block:
            slots[-1].end_block = next_window_block
            slots[-1].total_blocks = slots[-1].end_block - slots[-1].start_block + 1

        return slots


ALLOCATION_CLASSES = {
    "stake_based": StakeBased,
    "equal": EqualDistribution,
}


def get_allocation(allocation_type: str, config) -> BaseAllocation:
    """Create allocation instance from config"""
    if allocation_type not in ALLOCATION_CLASSES:
        bt.logging.warning(f"Unknown allocation {allocation_type}, using stake_based")
        allocation_type = "stake_based"

    allocation_class = ALLOCATION_CLASSES[allocation_type]
    return allocation_class(
        min_blocks_per_validator=config.allocation.min_blocks,
        validator_blacklist=config.blacklist,
        max_validators=config.allocation.max_validators,
    )
