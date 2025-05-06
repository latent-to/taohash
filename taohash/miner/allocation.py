import os
import argparse

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import bittensor as bt
from taohash.miner.models import MiningSlot, PoolTarget

if TYPE_CHECKING:
    from taohash.core.chain_data.pool_info import PoolInfo


class AllocationConfig:
    """
    Configuration class that defines the parameters for mining slot allocation strategies.

    This class manages the default values and CLI argument parsing for all allocation-related
    settings in the Taohash subnet. It controls:

    - Allocation strategy type (stake-based, equal, multi-pool)
    - Minimum blocks per validator to ensure fair distribution
    - Validator filtering criteria (min stake, max validators)
    - Multi-pool slot configuration (max pools per slot, min proportion)
    - Slot sizing parameters

    The configuration can be set via command-line arguments or environment variables
    """

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
    """
    Abstract base class that defines the interface for mining slot allocation strategies.

    This class provides the core functionality for distributing mining slots to validators
    in the Taohash subnet. It handles common operations like:

    - Filtering and sorting validators based on blacklist, stake, and validator permits.
    - Creating mining schedules based on the implemented allocation algorithm

    Each concrete allocation strategy must implement the abstract allocate_slots method
    to define its specific distribution logic (e.g., stake-based, equal distribution,
    or multi-pool allocation).

    The allocation strategy determines how miners distribute their hashrate across
    different validator pools in the network within a mining window.
    """

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
        metagraph: "bt.Metagraph",
    ) -> list["MiningSlot"]:
        """
        Creates a mining schedule by distributing available blocks among validator pools.

        This method serves as the main entry point for generating mining slots. It delegates
        the actual allocation logic to the strategy-specific `allocate_slots` method.

        Parameters:
            current_block: The current Bittensor block number
            available_blocks_this_window: Number of blocks available to allocate in this schedule
            next_window_block: The block number where the next allocation window begins
            pool_info: Dictionary mapping validator hotkeys to their pool information
            metagraph: The Bittensor metagraph containing network state and validator info

        Returns:
            A list of MiningSlot objects that define which validators to mine for during
            specific block ranges.
        """
        return self.allocate_slots(
            current_block,
            available_blocks_this_window,
            next_window_block,
            pool_info,
            metagraph,
        )

    def _filter_validators(
        self, pool_info: dict[str, "PoolInfo"], metagraph: "bt.Metagraph"
    ) -> dict[str, "PoolInfo"]:
        """
        Filters and sorts validators based on multiple criteria.

        This method performs several filtering operations to select eligible validators:

        1. Basic eligibility filters:
        - Excludes validators in the blacklist
        - Ensures validator exists in the metagraph
        - Verifies the validator has an active permit

        2. Stake-based filtering:
        - Applies minimum stake threshold to ensure validators have sufficient backing

        3. Sorting and limiting:
        - Sorts validators by total stake (descending)
        - Optionally limits to the top N validators based on configuration

        Parameters:
            pool_info: Dictionary mapping validator hotkeys to their mining pool information
            metagraph: Bittensor metagraph containing sub-network state

        Returns:
            A filtered and sorted dictionary of eligible validators with their pool information.
        """
        # Filter based on blacklist, metagraph, and validator permit
        filtered = {
            hotkey: info
            for hotkey, info in pool_info.items()
            if (
                hotkey not in self.validator_blacklist
                and hotkey in metagraph.hotkeys
                and metagraph.validator_permit[metagraph.hotkeys.index(hotkey)]
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
                if metagraph.total_stake[metagraph.hotkeys.index(hotkey)] >= min_stake
            }

        # Sort by stake
        sorted_validators = sorted(
            filtered.items(),
            key=lambda x: metagraph.total_stake[metagraph.hotkeys.index(x[0])],
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
        metagraph: "bt.Metagraph",
    ) -> list[MiningSlot]:
        """
        Abstract method that defines the core slot allocation logic for a specific strategy.

        This method is the heart of any allocation strategy and must be implemented by all
        concrete subclasses. It determines how available blocks are distributed among
        validator pools based on the strategy's allocation principles.

        The implementation should:
        - Use _filter_validators to get the eligible set of validators
        - Calculate block allocations according to the strategy's algorithm
        - Create MiningSlot objects to represent time periods allocated to specific validators
        - Ensure slots don't extend beyond next_window_block
        - Handle edge cases like insufficient remaining blocks

        Parameters:
            current_block: The current blockchain block number
            available_blocks: Total number of blocks available for allocation
            next_window_block: The block number where the next allocation window begins
            pool_info: Dictionary mapping validator hotkeys to their pool information
            metagraph: Bittensor metagraph containing sub-network state

        Returns:
            A list of non-overlapping MiningSlot objects that collectively span from
            current_block to at most next_window_block, with each slot defining which
            validator(s) to mine for during specific block ranges.
        """
        pass


class StakeBased(BaseAllocation):
    """
    Allocation strategy that distributes mining blocks proportionally based on stake weight.

    This is a greedy allocation approach that prioritizes validators with higher stake:

    1. Calculates a fair share of blocks for each validator based on their relative stake
       in the network (stake_validator / total_stake)
    2. Processes validators in descending stake order, allocating their fair share
       or at minimum the configured min_blocks_per_validator
    3. Ensures no validator receives less than the minimum blocks unless remaining
       blocks are insufficient
    4. If any blocks remain unallocated after processing all validators, they are
       added to the last validator's slot

    This strategy favors validators with higher stake, aligning mining rewards
    while maintaining a minimum allocation for smaller stakeholders.
    """

    def allocate_slots(
        self,
        current_block: int,
        available_blocks: int,
        next_window_block: int,
        pool_info: dict[str, "PoolInfo"],
        metagraph: "bt.Metagraph",
    ) -> list[MiningSlot]:
        filtered = self._filter_validators(pool_info, metagraph)
        if not filtered:
            return []

        slots = []
        current_pos = current_block
        remaining_blocks = available_blocks

        # Calculate total stake for selected validators
        total_stake = sum(
            metagraph.total_stake[metagraph.hotkeys.index(hotkey)]
            for hotkey in filtered
        )

        for hotkey, pool_info in filtered.items():
            if remaining_blocks < self.min_blocks_per_validator:
                break

            stake = metagraph.total_stake[metagraph.hotkeys.index(hotkey)]
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
    Advanced allocation strategy that enables mining for multiple validators simultaneously within a single slot.

    This strategy leverages proportional hashrate splitting to maximize decentralization and fairness.
    Unlike other strategies, it allows miners to direct portions of their hashrate to different
    validator pools concurrently

    Implementation details:

    1. Minimum Guarantee: Each validator initially receives min_blocks_per_validator blocks
    2. Water-Fill Distribution: Remaining blocks are allocated one-by-one to validators with
       the largest stake-to-allocation deficit, ensuring fair distribution based on stake weight
    3. Efficient Packing: Small quotas are bundled together into slots of min_slot_size blocks
    4. Multi-Pool Assignment: Up to max_pools_per_slot validators can share a single mining slot
    5. Proportional Allocation: Each validator in a slot receives hashrate proportional to their
       quota within that slot (must exceed min_proportion threshold)

    Note: Requires compatible mining proxy software capable of hashrate splitting. Currently,
    Braiins Proxy supports this functionality when multiple physical miners are connected.
    """

    def _water_fill(
        self,
        window: int,
        validator_list: list[str],
        metagraph: "bt.Metagraph",
    ) -> dict[str, int]:
        # Allocate min blocks to each validator
        quotas = {hk: self.min_blocks_per_validator for hk in validator_list}
        remaining = window - len(validator_list) * self.min_blocks_per_validator

        stake = {
            hk: metagraph.total_stake[metagraph.hotkeys.index(hk)]
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
        metagraph: "bt.Metagraph",
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
    Allocation strategy that distributes mining blocks equally among all eligible validators.

    This strategy implements a strictly egalitarian approach to block allocation.

    1. Divides the available blocks equally among all filtered validators
    2. Handles remainder by giving one extra block to the first N validators
       (where N is the remainder)
    3. Ensures each validator receives at least min_blocks_per_validator
    4. Creates sequential, non-overlapping slots with a single validator per slot

    Note that while this strategy ignores stake weights, validators still must meet
    the minimum stake and other eligibility requirements to be included.
    """

    def allocate_slots(
        self,
        current_block: int,
        available_blocks: int,
        next_window_block: int,
        pool_info: dict[str, "PoolInfo"],
        metagraph: "bt.Metagraph",
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
