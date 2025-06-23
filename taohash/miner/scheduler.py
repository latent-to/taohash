from typing import Optional, Union, TYPE_CHECKING
import socket

import bittensor as bt
from tabulate import tabulate

from taohash.miner.models import MiningSlot, MiningSchedule

if TYPE_CHECKING:
    from taohash.miner.storage import JsonStorage, RedisStorage
    from taohash.miner.allocation import BaseAllocation


class MiningScheduler:
    """
    Manages mining schedule creation and execution throughout the mining process.

    This class handles the creation of mining schedules based on the selected allocation
    strategy, tracks the current active slot, and ensures miners are directed to the
    appropriate validator pools as blocks progress. It also manages communication with
    proxy software when slots change.

    Attributes:
        config: Bittensor configuration
        storage: Storage interface for persisting schedules and pool information
        metagraph: The Bittensor metagraph containing network state and validator info
        allocation: Strategy for allocating mining slots to validators
        window_size: Number of blocks in each scheduling window
    """

    def __init__(
        self,
        config: "bt.Config",
        metagraph: "bt.MetagraphInfo",
        storage: Union["JsonStorage", "RedisStorage"],
        allocation: "BaseAllocation",
        window_size: int,
        proxy_manager=None,
    ):
        """
        Initialize the mining scheduler with required components.

        Args:
            config: Bittensor configuration
            metagraph: Network state with validator information
            storage: Interface for persisting schedules and pool info
            allocation: Strategy for allocating mining slots
            window_size: Number of blocks in each scheduling window
            proxy_manager: Optional interface to mining proxy software
        """
        self.config = config
        self.storage = storage
        self.proxy_manager = proxy_manager
        self.metagraph = metagraph
        self.allocation = allocation
        self.window_size = window_size

        # State management
        self.current_schedule: Optional[MiningSchedule] = None

    def create_schedule(self, current_block: int) -> Optional[MiningSchedule]:
        """
        Create a new mining schedule starting at the current block.

        Fetches validator pool information and uses the allocation strategy
        to generate a schedule of mining slots for the upcoming window.

        Args:
            current_block: The current blockchain block number

        Returns:
            A new MiningSchedule covering the upcoming window
        """
        # Use window size for scheduling
        available_blocks = self.window_size
        next_window_block = current_block + self.window_size

        pool_info = self.storage.get_latest_pool_info()
        if not pool_info:
            return None

        bt.logging.info("Checking pool availability for all validators...")
        reachable_pools = {}

        for hotkey, info in pool_info.items():
            domain = info.get("domain")
            port = info.get("port")

            if domain and port:
                if self._check_pool_liveness(domain, port):
                    reachable_pools[hotkey] = info
                    bt.logging.info(
                        f"✅ Pool reachable: {domain}:{port} (validator {hotkey[:8]} {info.get('username')})"
                    )
                else:
                    bt.logging.warning(
                        f"❌ Skipping validator {hotkey[:8]} ({info.get('username')}) - pool {domain}:{port} unreachable"
                    )
            else:
                bt.logging.warning(
                    f"Invalid pool info for validator {hotkey[:8]}: "
                    f"domain={domain}, port={port}"
                )

        if not reachable_pools:
            bt.logging.error("No validators with reachable pools found!")
            return None

        bt.logging.info(
            f"Found {len(reachable_pools)}/{len(pool_info)} validators with reachable pools"
        )

        slots = self.allocation.create_schedule(
            current_block=current_block,
            available_blocks_this_window=available_blocks,
            next_window_block=next_window_block,
            pool_info=reachable_pools,
            metagraph=self.metagraph,
        )

        schedule = MiningSchedule(slots, available_blocks, current_block)

        self.log_schedule(schedule)
        self.storage.save_schedule(current_block, schedule)
        return schedule

    def update_mining_schedule(
        self, current_block: int, metagraph: "bt.MetagraphInfo" = None
    ) -> Optional["MiningSlot"]:
        """
        Update the mining schedule and current slot based on the current block.

        Creates a new schedule if needed and updates the current slot.
        When the slot changes, triggers proxy configuration updates.

        Args:
            current_block: The current blockchain block number
            metagraph: Optional updated metagraph

        Returns:
            The new MiningSlot if it changed, None otherwise
        """
        if metagraph:
            self.metagraph = metagraph

        # Ensure valid schedule
        if self.current_schedule is None or (
            self.current_schedule.end_block is not None
            and current_block > self.current_schedule.end_block
        ):
            new_schedule = self.create_schedule(current_block)
            if not new_schedule:
                bt.logging.warning(
                    f"No validators available for scheduling at block {current_block}. Will retry later."
                )
                return None
            self.current_schedule = new_schedule

        # Check and update current slot
        changed_slot = self.current_schedule.update_current_slot(current_block)
        if changed_slot:
            missed_blocks = current_block - changed_slot.start_block

            base_message = (
                f"Switching mining slot at block {current_block}:\n"
                f"Blocks: {changed_slot.start_block} → {changed_slot.end_block} ({changed_slot.total_blocks} blocks)\n"
                f"Targets:"
            )

            for target in changed_slot.pool_targets:
                base_message += (
                    f"\n- {target.validator_hotkey}: "
                    f"{target.pool_info['extra_data']['full_username']} → {target.pool_info['pool_url']} "
                    f"({target.proportion:.1%})"
                )

            if missed_blocks > 0:
                base_message += f"\nMissed blocks: {missed_blocks} during recovery"

            bt.logging.warning(base_message)
            self.storage.save_schedule(current_block, self.current_schedule)
            self._on_slot_change(changed_slot)
            return changed_slot

        return None

    def log_schedule(self, schedule: MiningSchedule) -> None:
        """
        Print a formatted table of the mining schedule.

        This method provides a visual representation of the current mining schedule,
        showing which validators are targeted for mining during specific time periods.
        It helps miners understand their hashrate distribution across different validators.
        """
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
            "Proportion",
        ]

        rows = []
        for slot in schedule.slots:
            block_percentage = (
                (slot.end_block - slot.start_block + 1) / schedule.total_blocks * 100
            )
            for target in slot.pool_targets:
                rows.append(
                    [
                        target.validator_hotkey[:8],
                        f"{slot.end_block - slot.start_block + 1}",
                        f"{block_percentage:.1f}%",
                        f"{slot.start_block}-{slot.end_block}",
                        target.pool_info["extra_data"]["full_username"],
                        target.pool_info["pool_url"],
                        f"{target.proportion:.1%}",
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
        """
        Handle mining slot transitions by reconfiguring mining hardware.

        This method is called whenever the miner transitions to a new mining slot.
        It communicates with the mining proxy to redirect hashrate to new pools.

        Args:
            new_slot: The new active mining slot containing target pool information
        """
        if self.proxy_manager:
            success = self.proxy_manager.update_config(new_slot)
            if not success:
                bt.logging.warning("Failed to update proxy configuration")

    def _check_pool_liveness(self, domain: str, port: int) -> bool:
        """
        Check if a pool is reachable via TCP socket connection.

        Args:
            domain: The domain or IP address of the pool
            port: The port number of the pool

        Returns:
            bool: True if the pool is reachable, False otherwise
        """
        try:
            with socket.socket() as sock:
                sock.settimeout(5)
                result = sock.connect_ex((domain, port))
                return result == 0
        except Exception as e:
            bt.logging.debug(f"Pool check failed for {domain}:{port} - {e}")
            return False
