from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

import bittensor as bt
from tabulate import tabulate

if TYPE_CHECKING:
    from taohash.miner.models import MiningSlot
    from taohash.miner.storage import BaseStorage
    from taohash.miner.allocation import BaseAllocation


@dataclass
class MiningSchedule:
    slots: list["MiningSlot"]
    total_blocks: int
    created_at_block: int
    end_block: int

    def __init__(
        self, slots: list["MiningSlot"], total_blocks: int, created_at_block: int
    ):
        self.slots = slots
        self.total_blocks = total_blocks
        self.created_at_block = created_at_block
        self.end_block = created_at_block + total_blocks - 1

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


class MiningScheduler:
    """Manages mining schedule creation and updates."""

    def __init__(
        self,
        config: "bt.Config",
        metagraph: "bt.metagraph.Metagraph",
        storage: "BaseStorage",
        allocation: "BaseAllocation",
        window_size: int,
        proxy_manager=None,
    ):
        self.config = config
        self.storage = storage
        self.proxy_manager = proxy_manager
        self.metagraph = metagraph
        self.allocation = allocation
        self.window_size = window_size

        # State management
        self.current_schedule: Optional[MiningSchedule] = None
        self.current_slot: Optional["MiningSlot"] = None

    def create_schedule(self, current_block: int) -> MiningSchedule:
        """Create a new mining schedule"""
        # Use window size for scheduling
        available_blocks = self.window_size
        next_window_block = current_block + self.window_size

        pool_info = self.storage.get_latest_pool_info()
        if not pool_info:
            bt.logging.warning("No validators available for scheduling.")
            return MiningSchedule(
                slots=[], total_blocks=0, created_at_block=current_block
            )

        slots = self.allocation.create_schedule(
            current_block=current_block,
            available_blocks_this_window=available_blocks,
            next_window_block=next_window_block,
            pool_info=pool_info,
            metagraph=self.metagraph,
        )

        schedule = MiningSchedule(slots, available_blocks, current_block)

        self.log_schedule(schedule)
        return schedule

    def update_mining_schedule(
        self, current_block: int, metagraph: "bt.metagraph.Metagraph" = None
    ) -> Optional["MiningSlot"]:
        """Update the mining schedule if needed. Return the new slot if it changed."""
        if metagraph:
            self.metagraph = metagraph

        # Ensure valid schedule
        if (
            self.current_schedule is None
            or current_block > self.current_schedule.end_block
        ):
            self.current_schedule = self.create_schedule(current_block)

        # Current slot
        target_slot = self.current_schedule.get_slot_for_block(current_block)

        # Check for slot change
        if target_slot and target_slot != self.current_slot:
            bt.logging.warning(
                f"Switching mining slot at block {current_block}:\n"
                f"Validator: {target_slot.validator_hotkey}\n"
                f"Username: {target_slot.pool_info['extra_data']['full_username']}\n"
                f"Pool URL: {target_slot.pool_info['pool_url']}\n"
                f"Blocks: {target_slot.start_block} → {target_slot.end_block} ({target_slot.total_blocks} blocks)"
            )
            self.current_slot = target_slot
            self._on_slot_change(target_slot)
            return target_slot

        return None

    def log_schedule(self, schedule: MiningSchedule) -> None:
        """Print a formatted table of the mining schedule."""
        if not schedule.slots:
            bt.logging.warning("Empty schedule - no slots allocated")
            return

        headers = [
            "Validator",
            "Blocks",
            "Duration",
            "Start-End",
            "Username",
            "Pool URL",
        ]

        rows = []
        for slot in schedule.slots:
            block_percentage = (
                (slot.end_block - slot.start_block + 1) / schedule.total_blocks * 100
            )

            rows.append(
                [
                    slot.validator_hotkey[:8],
                    f"{slot.end_block - slot.start_block + 1}",
                    f"{block_percentage:.1f}%",
                    f"{slot.start_block}-{slot.end_block}",
                    slot.pool_info["extra_data"]["full_username"],
                    f"{slot.pool_info['pool_url']}",
                ]
            )

        # Summary
        rows.append(
            [
                "TOTAL",
                str(schedule.total_blocks),
                "100%",
                f"{schedule.created_at_block}-{schedule.end_block}",
                "",
                "",
            ]
        )

        table = tabulate(
            rows, headers=headers, tablefmt="grid", numalign="right", stralign="left"
        )

        bt.logging.info(
            f"\nMining Schedule (created at block {schedule.created_at_block}):\n"
            f"Total Blocks: {schedule.total_blocks}\n"
            f"Validators: {len(schedule.slots)}\n"
            f"{table}"
        )

    def _on_slot_change(self, new_slot: "MiningSlot") -> None:
        """Handle slot change events."""
        if self.proxy_manager:
            success = self.proxy_manager.update_config(new_slot)
            if not success:
                bt.logging.warning("Failed to update proxy configuration")
