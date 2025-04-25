from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
import argparse
import os

import bittensor as bt
from taohash.miner.models import MiningSlot, PoolTarget

if TYPE_CHECKING:
    from taohash.core.chain_data.pool_info import PoolInfo


class AllocationConfig:
    """Configuration holder for allocation parameters"""

    DEFAULT_TYPE = "stake_based"
    DEFAULT_MIN_BLOCKS = 40
    DEFAULT_MAX_VALIDATORS = None
    DEFAULT_MIN_STAKE = 500
    DEFAULT_MAX_POOLS_PER_SLOT = 3
    DEFAULT_MIN_PROPORTION = 0.03
    DEFAULT_MIN_SLOT_SIZE = 120

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser") -> None:
        """Add common allocation arguments to parser"""
        allocation_group = parser.add_argument_group("allocation")

        allocation_group.add_argument(
            "--allocation.type",
            type=str,
            choices=[
                "stake_based",
                "equal",
                "stake_based_multi",
            ],
            default=os.getenv("ALLOCATION_TYPE", cls.DEFAULT_TYPE),
            help="Allocation type",
        )

        allocation_group.add_argument(
            "--allocation.min_blocks",
            type=int,
            default=os.getenv("ALLOCATION_MIN_BLOCKS", cls.DEFAULT_MIN_BLOCKS),
            help="Minimum blocks to allocate per validator",
        )

        allocation_group.add_argument(
            "--allocation.max_validators",
            type=int,
            default=os.getenv("ALLOCATION_MAX_VALIDATORS", cls.DEFAULT_MAX_VALIDATORS)
            or None,
            help="Maximum number of validators to include (None for all)",
        )

        allocation_group.add_argument(
            "--allocation.min_stake",
            type=float,
            default=os.getenv("ALLOCATION_MIN_STAKE", cls.DEFAULT_MIN_STAKE),
            help="Minimum stake required for a validator to be included",
        )
        allocation_group.add_argument(
            "--allocation.max_pools_per_slot",
            type=int,
            default=int(
                os.getenv(
                    "ALLOCATION_MAX_POOLS_PER_SLOT", cls.DEFAULT_MAX_POOLS_PER_SLOT
                )
            ),
            help="Maximum distinct pools allowed inside one mining slot",
        )
        allocation_group.add_argument(
            "--allocation.min_proportion",
            type=float,
            default=float(
                os.getenv("ALLOCATION_MIN_PROPORTION", cls.DEFAULT_MIN_PROPORTION)
            ),
            help="Minimum proportion (0-1) a pool must have inside a slot to be inserted",
        )
        allocation_group.add_argument(
            "--allocation.min_slot_size",
            type=int,
            default=int(
                os.getenv("ALLOCATION_MIN_SLOT_SIZE", cls.DEFAULT_MIN_SLOT_SIZE)
            ),
            help="Minimum slot size",
        )


class BaseAllocation(ABC):
    """Base class for allocation strategies"""

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser") -> None:
        AllocationConfig.add_args(parser)

    def __init__(
        self,
        config: Any,
    ):
        self.config = config
        self.min_blocks_per_validator = config.allocation.min_blocks
        self.validator_blacklist = getattr(config, "blacklist", []) or []
        self.max_validators = config.allocation.max_validators

    def create_schedule(
        self,
        current_block: int,
        available_blocks_this_window: int,
        next_window_block: int,
        pool_info: dict[str, "PoolInfo"],
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
        self, pool_info: dict[str, "PoolInfo"], metagraph: "bt.metagraph.Metagraph"
    ) -> dict[str, "PoolInfo"]:
        """Filter and sort validators based on criteria"""
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

        # Apply min stake filter if required
        min_stake = self.config.allocation.min_stake
        if min_stake > 0:
            filtered = {
                hotkey: info
                for hotkey, info in filtered.items()
                if metagraph.neurons[metagraph.hotkeys.index(hotkey)].total_stake.tao
                >= min_stake
            }

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
        pool_info: dict[str, "PoolInfo"],
        metagraph: "bt.metagraph.Metagraph",
    ) -> list[MiningSlot]:
        """Strategy-specific slot allocation logic"""
        pass


class StakeBased(BaseAllocation):
    """
    Allocates blocks proportionally based on stake.
    This is a greedy strategy:
        1. Divides available blocks by fair share of each pool based on stake
        2. Allocates the top validators first
        3. If at any point, the remaining blocks are less than the min_blocks_per_validator, add remaining to the last validator.
    """

    def allocate_slots(
        self,
        current_block: int,
        available_blocks: int,
        next_window_block: int,
        pool_info: dict[str, "PoolInfo"],
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
                validator_hotkey=hotkey, proportion=1.0, pool_info=pool_info
            )

            slots.append(
                MiningSlot(
                    start_block=current_pos,
                    end_block=end_block,
                    total_blocks=blocks_allocated,
                    pool_targets=[pool_target],
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


class MultiPoolStakeAllocation(BaseAllocation):
    """
    This strategy utilises "proportions" and have more than one pools per slot.
    This is useful for miners who have the capability in their proxies to split hashrate.
    As of now, Braiins Proxy only supports this if you have more than one miner connected to the proxy farm.

    Steps:
        1. Min Allocation: Each validator gets min_blocks_per_validator irrepective of stake.
        2. Water Fill: Remaining blocks are distributed one by one to the validator who is furthest below its stake share.
        3. Bundle small quotas together
        4. Pack quotas into min_slot_size slots with max_pools_per_slot
        5. Set proportions inside each slot
        6. Finalise list of slots.
    """

    def _water_fill(
        self,
        window: int,
        validator_list: list[str],
        metagraph: "bt.metagraph.Metagraph",
    ) -> dict[str, int]:
        # Allocate min blocks to each validator
        quotas = {hk: self.min_blocks_per_validator for hk in validator_list}
        remaining = window - len(validator_list) * self.min_blocks_per_validator

        stake = {
            hk: metagraph.neurons[metagraph.hotkeys.index(hk)].total_stake.tao
            for hk in validator_list
        }
        total_stake = sum(stake.values())

        # Progressive fill: allocate 1 block to validator furthest below its ideal share
        while remaining > 0:
            hk = max(
                quotas,
                key=lambda h: stake[h] / total_stake - quotas[h] / window,
            )
            quotas[hk] += 1
            remaining -= 1
        return quotas

    def allocate_slots(
        self,
        current_block: int,
        available_blocks: int,
        next_window_block: int,
        pool_info: dict[str, "PoolInfo"],
        metagraph: "bt.metagraph.Metagraph",
    ) -> list[MiningSlot]:
        validators = self._filter_validators(pool_info, metagraph)
        if not validators:
            return []

        # Get per-validator quota via water-fill
        quotas = self._water_fill(available_blocks, list(validators), metagraph)

        # Smallest quotas first so we pack little guys together
        pools_by_quota_asc = sorted(quotas.items(), key=lambda kv: kv[1])

        slots: list[MiningSlot] = []
        slot_start = current_block
        pending_slot_allocations: list[tuple[str, int]] = []
        pending_blocks = 0

        max_pools_per_slot = self.config.allocation.max_pools_per_slot
        min_slot_size = self.config.allocation.min_slot_size
        min_proportion = self.config.allocation.min_proportion

        # Helper: convert pending allocations to MiningSlot and reset
        def create_slot_from_pending():
            nonlocal slot_start, pending_slot_allocations, pending_blocks
            if not pending_slot_allocations:
                return
            total = pending_blocks

            # Drop small shares below min_proportion (if any)
            pool_targets = [
                PoolTarget(hk, q / total, validators[hk])
                for hk, q in pending_slot_allocations
                if q / total >= min_proportion
            ]
            if not pool_targets:
                # Put the tiny remainder into previous slot
                slots[-1].end_block += total
                slots[-1].total_blocks += total
            else:
                slots.append(
                    MiningSlot(
                        start_block=slot_start,
                        end_block=slot_start + total - 1,
                        total_blocks=total,
                        pool_targets=pool_targets,
                    )
                )
                slot_start += total
            pending_slot_allocations.clear()
            pending_blocks = 0

        # Pack quotas into slots (main packing loop)
        while pools_by_quota_asc:
            hk, need = pools_by_quota_asc.pop(0)

            while need > 0:  # Large quotas may span several slots
                capacity = min_slot_size - pending_blocks
                slots_free = max_pools_per_slot - len(pending_slot_allocations)

                # If this validator can't fit, close current slot & start new one
                if capacity == 0 or slots_free == 0:
                    create_slot_from_pending()
                    continue

                take = min(need, capacity)
                pending_slot_allocations.append((hk, take))
                pending_blocks += take
                need -= take

                if pending_blocks == min_slot_size:
                    create_slot_from_pending()  # Slot is full -> move on

        create_slot_from_pending()  # Flush the trailing partial slot

        if slots and slots[-1].end_block > next_window_block:
            slots[-1].end_block = next_window_block
            slots[-1].total_blocks = slots[-1].end_block - slots[-1].start_block + 1

        return slots


# TODO: EMA Stake Based
class EMAStakeBased(BaseAllocation):
    """Allocates blocks proportionally based on EMA of stake"""

    pass


class EqualDistribution(BaseAllocation):
    """
    Allocates blocks equally among targets.
    This is a fair strategy which does not take into account stake.
    It just equally distributes the blocks among the targets.
    """

    def allocate_slots(
        self,
        current_block: int,
        available_blocks: int,
        next_window_block: int,
        pool_info: dict[str, "PoolInfo"],
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
                validator_hotkey=hotkey, proportion=1.0, pool_info=pool_info
            )

            slots.append(
                MiningSlot(
                    start_block=current_pos,
                    end_block=end_block,
                    total_blocks=blocks_allocated,
                    pool_targets=[pool_target],
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
    "stake_based_multi": MultiPoolStakeAllocation,
}


def get_allocation(allocation_type: str, config) -> BaseAllocation:
    """Create allocation instance from config"""
    if allocation_type not in ALLOCATION_CLASSES:
        bt.logging.warning(f"Unknown allocation {allocation_type}, using stake_based")
        allocation_type = "stake_based"

    allocation_class = ALLOCATION_CLASSES[allocation_type]
    return allocation_class(config=config)
