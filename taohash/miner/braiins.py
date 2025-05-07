import argparse
import traceback

from bittensor import logging
from dotenv import load_dotenv

from taohash.core.chain_data.pool_info import get_all_pool_info, PoolInfo
from taohash.core.constants import BLOCK_TIME
from taohash.core.pool import PoolIndex
from taohash.miner import BaseMiner
from taohash.miner.allocation import get_allocation
from taohash.miner.proxy.braiins_farm.controller import BraiinsProxyManager
from taohash.miner.scheduler import MiningScheduler

DEFAULT_SYNC_FREQUENCY = 6


class BraiinsMiner(BaseMiner):
    """
    Braiins BTC Miner implementation.

    This miner targets the Braiins pool ecosystem for Bitcoin mining,
    handling proxy connections and scheduling mining across validators.
    """

    def __init__(self):
        """
        Initialize the Braiins miner with configuration and setup.

        Process:
            1. Perform base miner initialization
            2. Set up Braiins-specific proxy manager if enabled and storage
            3. Initialize mining scheduler with appropriate allocation strategy
        """
        # Base miner initialization
        super().__init__()

        self.blocks_per_window = self.tempo * 2

        # Braiins-specific setup
        self.proxy_manager = None
        if self.config.use_proxy:
            logging.info(
                f"Setting up proxy manager with path: {self.config.proxy_base_path}"
            )
            self.proxy_manager = BraiinsProxyManager(
                config=self.config,
                proxy_base_path=self.config.proxy_base_path,
                proxy_port=self.config.proxy_port,
            )

        allocation_type = get_allocation(self.config.allocation.type, self.config)
        self.mining_scheduler = MiningScheduler(
            config=self.config,
            window_size=self.blocks_per_window,
            storage=self.storage,
            allocation=allocation_type,
            metagraph=self.metagraph,
            proxy_manager=self.proxy_manager,
        )

    def add_args(self, parser: argparse.ArgumentParser):
        """Add Braiins-specific arguments to the parser."""
        super().add_args(parser)
        BraiinsProxyManager.add_args(parser)

    def get_target_pools(self) -> dict[str, PoolInfo]:
        """
        Fetch Braiins pools from the chain.

        Returns:
            Dict: Dictionary of Braiins pool information indexed by validator hotkeys

        Process:
            1. Get all pools from base implementation
            2. Filter to include only Braiins pools (PoolIndex.Braiins)
            3. Enhance pool data with worker-specific username
        """
        all_pools: dict[str, PoolInfo] = get_all_pool_info(
            self.subtensor,
            self.config.netuid,
        )
        if not all_pools:
            logging.warning("No validators found with pool information")
            return {}

        # Filter from metagraph and only include btc braiins pools
        target_pools = {}
        for hotkey, pool_info in all_pools.items():
            if (
                hotkey in self.metagraph.hotkeys
                and pool_info.pool_index == PoolIndex.Braiins
            ):
                pool_info.extra_data["full_username"] = (
                    f"{pool_info.username}.{self.worker_id}"
                )
                target_pools[hotkey] = pool_info.to_json()
        return target_pools

    def restore_schedule(self) -> None:
        """
        Restore the mining schedule from storage.

        Process:
            1. Load the latest schedule from storage if recovery is enabled
            2. Update the mining scheduler with the recovered schedule
            3. Check if the schedule is still valid or needs updating
            4. Report the recovery status and any slot changes
        """
        if self._recover_schedule:
            recovered_schedule = self.storage.load_latest_schedule()
            if recovered_schedule:
                self.mining_scheduler.current_schedule = recovered_schedule
                logging.success(
                    f"Recovered schedule from creation block {recovered_schedule.created_at_block}"
                )
            else:
                logging.info("No schedule to recover; will create fresh.")

            changed_slot = self.mining_scheduler.update_mining_schedule(
                current_block=self.current_block,
                metagraph=self.metagraph,
            )
            if self.mining_scheduler.current_schedule != recovered_schedule:
                logging.warning(
                    "Recovered schedule was outdated - created new schedule."
                )
            elif changed_slot:
                logging.success(
                    f"Mining slot updated at block {self.current_block} from recovered schedule."
                )
            else:
                current_slot = self.mining_scheduler.current_schedule.current_slot
                logging.info(
                    f"No slot change detected - current slot is still valid: \n{current_slot}"
                )

    def sync_and_refresh(self) -> None:
        """
        Sync metagraph, fetch pools, and update mining schedule.

        Process:
            1. Sync metagraph to get latest network state
            2. Fetch current target pools from validators
            3. Save pool data to persistent storage
            4. Handle first sync and schedule recovery
            5. Update mining schedule based on current network state
        """
        self.metagraph = self.subtensor.get_metagraph_info(netuid=self.config.netuid)
        self.current_block = self.metagraph.block
        logging.info(f"Syncing at block {self.current_block}")

        target_pools = self.get_target_pools()
        if target_pools:
            self.storage.save_pool_data(self.current_block, target_pools)
            logging.info(f"Saved pool data on block: {self.current_block}")

        if self.mining_scheduler and target_pools:
            if self._first_sync:
                self._first_sync = False
                if self._recover_schedule:
                    self.restore_schedule()

            changed_slot = self.mining_scheduler.update_mining_schedule(
                current_block=self.current_block,
                metagraph=self.metagraph,
            )
            if changed_slot:
                logging.success(f"Mining slot updated at block {self.current_block}")

    def get_next_sync_block(self) -> tuple[int, str]:
        """
        Get the next block we should sync at and the reason.

        Returns:
            tuple[int, str]: The next block to sync at and a string explaining the reason

        Process:
            1. Calculate next regular sync interval
            2. Check for upcoming epoch boundaries
            3. Check for slot changes or window boundaries
            4. Return the earliest event with its explanation
        """
        if not self.mining_scheduler.current_schedule:
            next_sync = self.current_block + (
                10 * 60 // BLOCK_TIME
            )  # Check again after 10 minutes
            sync_reason = "No schedule"
            return next_sync, sync_reason

        next_sync = self.current_block + (
            self.blocks_per_sync - (self.current_block % self.blocks_per_sync)
        )
        sync_reason = "Regular interval"

        blocks_until_epoch = self.blocks_until_next_epoch()
        if blocks_until_epoch > 0:
            epoch_block = self.current_block + blocks_until_epoch
            if epoch_block < next_sync:
                next_sync = epoch_block
                sync_reason = "Epoch boundary"

        # Check slot changes
        if (
            self.mining_scheduler
            and self.mining_scheduler.current_schedule
            and self.mining_scheduler.current_schedule.current_slot
        ):
            # If we have a mining slot, check when it ends
            current_schedule = self.mining_scheduler.current_schedule
            slot_end = current_schedule.current_slot.end_block + 1
            if self.current_block <= slot_end < next_sync:
                next_sync = slot_end
                if slot_end == current_schedule.end_block + 1:
                    sync_reason = "New window"
                else:
                    sync_reason = "Slot change"

        return next_sync, sync_reason

    def run(self) -> None:
        """
        Run the main mining loop.

        Process:
            1. Perform initial sync to get latest chain state
            2. Calculate the next sync point
            3. Enter main loop:
                - Wait for next sync block
                - Update metagraph and pool data
                - Update mining schedule if needed
                - Calculate next sync point
                - Log mining status and performance
        """
        logging.info("Starting main loop")

        self.sync_and_refresh()
        logging.info(f"Performed initial sync at block {self.current_block}")

        next_sync_block, sync_reason = self.get_next_sync_block()
        logging.info(f"Next sync at block: {next_sync_block} | Reason: {sync_reason}")

        while True:
            try:
                if self.subtensor.wait_for_block(next_sync_block):
                    self.sync_and_refresh()
                    next_sync_block, sync_reason = self.get_next_sync_block()

                    logging.info(
                        f"Block: {self.current_block} | "
                        f"Next sync: {next_sync_block} | "
                        f"Reason: {sync_reason} | "
                        f"Incentive: {self.metagraph.incentives[self.uid]} | "
                        f"Blocks since epoch: {self.metagraph.blocks_since_last_step}"
                    )
                else:
                    logging.warning("Timeout waiting for block, retrying...")
                    continue

            except KeyboardInterrupt:
                logging.success("Miner killed by keyboard interrupt.")
                break
            except Exception:
                logging.error(traceback.format_exc())
                continue


if __name__ == "__main__":
    load_dotenv()
    miner = BraiinsMiner()
    miner.run()
