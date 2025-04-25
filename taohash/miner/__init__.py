import argparse
import os

from bittensor import Subtensor, config, logging
from bittensor_wallet.bittensor_wallet import Wallet

from taohash.miner.allocation import BaseAllocation
from taohash.miner.storage import get_miner_storage

DEFAULT_SYNC_FREQUENCY = 6


class BaseMiner:
    def __init__(self):
        """Initialize the base miner with configuration and setup."""
        self.config = self.get_config()
        self.setup_logging()
        self.setup_bittensor_objects()
        self.storage = get_miner_storage(storage_type="json", config=self.config)

        self.worker_id = self.create_worker_id()
        self.tempo = self.subtensor.tempo(self.config.netuid)
        self.current_block = 0
        self.blocks_per_sync = self.tempo // self.config.sync_frequency

        self._first_sync = True
        self._recover_schedule = self.config.recover_schedule

    def get_config(self):
        """Create and parse configuration."""
        parser = argparse.ArgumentParser()
        self.add_args(parser)
        return config(parser)

    def add_args(self, parser: argparse.ArgumentParser):
        """Base miner argument definitions."""
        parser.add_argument(
            "--netuid",
            type=int,
            default=os.getenv("NETUID", 14),
            help="The chain subnet uid.",
        )
        # Sync frequency
        parser.add_argument(
            "--sync_frequency",
            type=int,
            default=os.getenv("SYNC_FREQUENCY", DEFAULT_SYNC_FREQUENCY),
            help=f"Number of times to sync and update pool info per epoch (1-359). Default is {DEFAULT_SYNC_FREQUENCY} times per epoch.",
        )
        parser.add_argument(
            "--no-recover_schedule",
            action="store_false",
            dest="recover_schedule",
            default=os.getenv("RECOVER_SCHEDULE", "true").lower() == "true",
            help="Disable schedule recovery between restarts.",
        )
        parser.add_argument(
            "--blacklist",
            type=str,
            nargs="+",
            default=os.getenv("BLACKLIST", "").split(",")
            if os.getenv("BLACKLIST")
            else [],
            help="List of validator hotkeys to exclude from mining",
        )

        # Add other base arguments
        BaseAllocation.add_args(parser)
        RedisStorage.add_args(parser)
        Subtensor.add_args(parser)
        logging.add_args(parser)
        Wallet.add_args(parser)

    def setup_logging(self) -> None:
        """Set up logging for the miner."""
        logging(config=self.config, logging_dir=self.config.full_path)
        logging.info(
            f"Running miner for subnet: {self.config.netuid} on network: {self.config.subtensor.network} with config:\n{self.config}"
        )
        logging.info(f"Sync frequency: {self.config.sync_frequency} times per epoch")

    def setup_bittensor_objects(self) -> None:
        """Setup Bittensor objects."""
        logging.info("Setting up Bittensor objects")

        # Initialize wallet.
        self.wallet = Wallet(config=self.config)
        logging.info(f"Wallet: {self.wallet}")

        # Initialize subtensor.
        self.subtensor = Subtensor(config=self.config)
        logging.info(f"Subtensor: {self.subtensor}")

        # Initialize metagraph.
        self.metagraph = self.subtensor.metagraph(self.config.netuid)
        logging.info(f"Metagraph: {self.metagraph}")

        if self.wallet.hotkey.ss58_address not in self.metagraph.hotkeys:
            logging.error(
                f"\nYour miner: {self.wallet} is not registered to chain connection: {self.subtensor}\n"
                f"Run 'btcli subnet register' and try again."
            )
            exit()

        self.uid = self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address)
        self.current_block = self.metagraph.block.item()
        logging.info(f"Running miner on uid: {self.uid}")

    def create_worker_id(self) -> str:
        """Create a worker ID based on the miner's hotkey address."""
        hotkey = self.wallet.hotkey.ss58_address
        return hotkey[:4] + hotkey[-4:]

    def blocks_until_next_epoch(self) -> int:
        """Get number of blocks until new tempo starts"""
        blocks = self.subtensor.subnet(self.config.netuid).blocks_since_last_step
        return self.tempo - blocks
