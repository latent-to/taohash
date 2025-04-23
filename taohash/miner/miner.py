import os
import argparse
import traceback
from typing import Dict

import bittensor as bt

import taohash.core.constants as constants
from taohash.core.chain_data.pool_info import get_all_pool_info, PoolInfo
from taohash.miner.storage import RedisStorage
from taohash.miner.scheduler import MiningScheduler
from taohash.miner.proxy.braiins_farm.controller import BraiinsProxyManager
from taohash.miner.allocation import BaseAllocation, get_allocation
from taohash.core.pool import PoolIndex


class Miner:
    def __init__(self):
        """Initialize the miner with configuration and setup."""
        self.config = self.get_config()
        self.setup_logging()
        self.setup_bittensor_objects()
        self.worker_id = self.create_worker_id()
        self.tempo = self.subtensor.tempo(self.config.netuid)
        self.current_block = 0
        self.blocks_per_sync = self.tempo // self.config.sync_frequency
        self.blocks_per_window = self.tempo * 2
        self.storage = RedisStorage(self.config)

        self.proxy_manager = None
        if self.config.use_proxy:
            bt.logging.info(
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
        self._first_sync = True
        self._recover_schedule = self.config.recover_schedule

    def get_config(self):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--netuid", type=int, default=1, help="The chain subnet uid."
        )
        # Sync frequency
        parser.add_argument(
            "--sync_frequency",
            type=int,
            default=constants.DEFAULT_SYNC_FREQUENCY,
            help=f"Number of times to sync and update pool info per epoch (1-359). Default is {constants.DEFAULT_SYNC_FREQUENCY} times per epoch.",
        )
        parser.add_argument(
            "--no-recover_schedule",
            action="store_false",
            dest="recover_schedule",
            help="Disable schedule recovery between restarts.",
        )
        parser.add_argument(
            "--blacklist",
            type=str,
            nargs="+",
            default=[],
            help="List of validator hotkeys to exclude from mining",
        )
        BaseAllocation.add_args(parser)
        BraiinsProxyManager.add_args(parser)
        RedisStorage.add_args(parser)
        bt.subtensor.add_args(parser)
        bt.logging.add_args(parser)
        bt.wallet.add_args(parser)
        config = bt.config(parser)

        # Logging directory
        config.full_path = os.path.expanduser(
            "{}/{}/{}/netuid{}/{}".format(
                config.logging.logging_dir,
                config.wallet.name,
                config.wallet.hotkey_str,
                config.netuid,
                "miner",
            )
        )
        os.makedirs(config.full_path, exist_ok=True)

        return config

    def setup_logging(self) -> None:
        """Set up logging for the miner."""
        bt.logging(config=self.config, logging_dir=self.config.full_path)
        bt.logging.info(
            f"Running miner for subnet: {self.config.netuid} on network: {self.config.subtensor.network}"
        )
        bt.logging.info(f"Sync frequency: {self.config.sync_frequency} times per epoch")

    def setup_bittensor_objects(self) -> None:
        bt.logging.info("Setting up Bittensor objects")

        # Initialize wallet.
        self.wallet = bt.wallet(config=self.config)
        bt.logging.info(f"Wallet: {self.wallet}")

        # Initialize subtensor.
        self.subtensor = bt.subtensor(config=self.config)
        bt.logging.info(f"Subtensor: {self.subtensor}")

        # Initialize metagraph.
        self.metagraph = self.subtensor.metagraph(self.config.netuid)
        bt.logging.info(f"Metagraph: {self.metagraph}")

        if self.wallet.hotkey.ss58_address not in self.metagraph.hotkeys:
            bt.logging.error(
                f"\nYour miner: {self.wallet} is not registered to chain connection: {self.subtensor}\n"
                f"Run 'btcli subnet register' and try again."
            )
            exit()

        self.my_subnet_uid = self.metagraph.hotkeys.index(
            self.wallet.hotkey.ss58_address
        )
        self.current_block = self.metagraph.block.item()
        bt.logging.info(f"Running miner on uid: {self.my_subnet_uid}")

    def create_worker_id(self) -> str:
        """Create a worker ID based on the miner's hotkey address."""
        hotkey = self.wallet.hotkey.ss58_address
        return hotkey[:4] + hotkey[-4:]

    # They can do it in the scheduler
    def get_target_pools(self):
        """Fetch pools from the chain"""
        all_pools: Dict[str, PoolInfo] = get_all_pool_info(
            self.subtensor,
            self.config.netuid,
        )
        if not all_pools:
            bt.logging.warning("No validators found with pool information")
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

    def restore_schedule(self):
        """Restore the schedule from storage."""
        if self._recover_schedule:
            recovered_schedule = self.storage.load_latest_schedule()
            if recovered_schedule:
                self.mining_scheduler.current_schedule = recovered_schedule
                bt.logging.success(
                    f"Recovered schedule from creation block {recovered_schedule.created_at_block}"
                )
                changed_slot = self.mining_scheduler.update_mining_schedule(
                    current_block=self.current_block,
                    metagraph=self.metagraph,
                )
                if self.mining_scheduler.current_schedule != recovered_schedule:
                    bt.logging.warning(
                        "Recovered schedule was outdated - created new schedule."
                    )
                elif changed_slot:
                    bt.logging.success(
                        f"Mining slot updated at block {self.current_block} from recovered schedule."
                    )
                else:
                    bt.logging.info(
                        "No slot change detected - current slot is still valid."
                    )
            else:
                bt.logging.info("No schedule to recover; will create fresh.")

    def sync_and_refresh(self) -> int:
        """Sync metagraph and collect pool data."""
        self.metagraph.sync()
        self.current_block = self.metagraph.block.item()
        bt.logging.info(f"Syncing at block {self.current_block}")

        target_pools = self.get_target_pools()
        if target_pools:
            self.storage.save_pool_data(self.current_block, target_pools)
            bt.logging.info(f"Saved pool data on block: {self.current_block}")

        if self.mining_scheduler:
            if self._first_sync:
                self._first_sync = False
                if self._recover_schedule:
                    self.restore_schedule()
                    return

            changed_slot = self.mining_scheduler.update_mining_schedule(
                current_block=self.current_block,
                metagraph=self.metagraph,
            )
            if changed_slot:
                bt.logging.success(f"Mining slot updated at block {self.current_block}")
        return 

    def blocks_until_next_epoch(self) -> int:
        """Get number of blocks until new tempo starts"""
        blocks = self.subtensor.subnet(self.config.netuid).blocks_since_last_step
        return self.tempo - blocks

    def get_next_sync_block(self) -> tuple[int, str]:
        """Get the next block we should sync at and the reason."""
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
            if slot_end >= self.current_block and slot_end < next_sync:
                next_sync = slot_end
                if slot_end == current_schedule.end_block + 1:
                    sync_reason = "New window"
                else:
                    sync_reason = "Slot change"

        return next_sync, sync_reason

    def run(self) -> None:
        """Run the main miner loop."""
        bt.logging.info("Starting main loop")

        self.sync_and_refresh()
        bt.logging.info(f"Performed initial sync at block {self.current_block}")

        next_sync_block, sync_reason = self.get_next_sync_block()
        bt.logging.info(
            f"Next sync at block: {next_sync_block} | Reason: {sync_reason}"
        )

        while True:
            try:
                if self.subtensor.wait_for_block(next_sync_block):
                    self.sync_and_refresh()
                    next_sync_block, sync_reason = self.get_next_sync_block()

                    bt.logging.info(
                        f"Block: {self.current_block} | "
                        f"Next sync: {next_sync_block} | "
                        f"Reason: {sync_reason} | "
                        f"Incentive: {self.metagraph.I[self.my_subnet_uid]} | "
                        f"Blocks since epoch: {self.metagraph.blocks_since_last_step}"
                    )
                else:
                    bt.logging.warning("Timeout waiting for block, retrying...")
                    continue

            except KeyboardInterrupt:
                bt.logging.success("Miner killed by keyboard interrupt.")
                break
            except Exception as e:
                bt.logging.error(traceback.format_exc())
                continue


if __name__ == "__main__":
    miner = Miner()
    miner.run()

# TODO: Nice hash, proxy miner, base miner
# TODO: min stake for miners
