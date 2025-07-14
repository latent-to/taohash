import argparse
import os
from typing import Optional

from bittensor import Subtensor, config, logging
from bittensor_wallet.bittensor_wallet import Wallet

from taohash.miner.storage import get_miner_storage, BaseJsonStorage, BaseRedisStorage
from taohash.core.chain_data.pool_info import get_pool_info, PoolInfo

DEFAULT_SYNC_FREQUENCY = 6


class BaseMiner:
    def __init__(self):
        """Initialize the base miner with configuration and setup."""
        self.config = self.get_config()
        self.setup_logging()

        self.wallet = None
        self.metagraph = None
        self.uid = None
        self.pool_hotkey = None

        self.subtensor = self.setup_bittensor_objects()
        self.storage = get_miner_storage(
            storage_type=self.config.storage, config=self.config
        )
        self.worker_id = self.create_worker_id()
        self.tempo = self.subtensor.tempo(self.config.netuid)
        self.current_block = 0
        self.blocks_per_sync = self.tempo // self.config.sync_frequency

    def get_config(self):
        """Create and parse configuration."""
        parser = argparse.ArgumentParser(conflict_handler="resolve")
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
            "--storage",
            type=str,
            choices=["json", "redis"],
            default=os.getenv("STORAGE_TYPE", "json"),
            help="Storage type to use (json or redis)",
        )

        # Add other base arguments
        BaseRedisStorage.add_args(parser)
        BaseJsonStorage.add_args(parser)
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

    def setup_bittensor_objects(self) -> "Subtensor":
        """Setup Bittensor objects."""
        logging.info("Setting up Bittensor objects")

        # Initialize wallet.
        self.wallet = Wallet(config=self.config)
        logging.info(f"Wallet: {self.wallet}")

        # Initialize subtensor.
        self.subtensor = Subtensor(config=self.config)
        logging.info(f"Subtensor: {self.subtensor}")

        # Initialize metagraph.
        self.metagraph = self.subtensor.get_metagraph_info(netuid=self.config.netuid)
        logging.info(
            f"Metagraph: "
            f"<netuid:{self.metagraph.netuid}, "
            f"n:{len(self.metagraph.axons)}, "
            f"block:{self.metagraph.block}, "
            f"network: {self.subtensor.network}>"
        )

        if self.wallet.hotkey.ss58_address not in self.metagraph.hotkeys:
            logging.error(
                f"\nYour miner: {self.wallet} is not registered to chain connection: {self.subtensor}\n"
                f"Run 'btcli subnet register' and try again."
            )
            exit()

        self.uid = self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address)
        self.current_block = self.metagraph.block
        logging.info(f"Running miner on uid: {self.uid}")
        return self.subtensor

    def create_worker_id(self) -> str:
        """Create a worker ID based on the miner's hotkey address."""
        hotkey = self.wallet.hotkey.ss58_address
        return hotkey[:4] + hotkey[-4:]

    def blocks_until_next_epoch(self) -> int:
        """Get number of blocks until new tempo starts"""
        blocks = self.subtensor.subnet(self.config.netuid).blocks_since_last_step
        return self.tempo - blocks

    def get_owner_hotkey(self) -> Optional[int]:
        """Get the hotkey of the subnet owner."""
        try:
            sn_owner_hotkey = self.subtensor.query_subtensor(
                "SubnetOwnerHotkey",
                params=[self.config.netuid],
            )
            return sn_owner_hotkey
        except Exception as e:
            logging.error(f"Error getting subnet owner hotkey: {e}")
            return None

    def get_subnet_pool(self) -> Optional[PoolInfo]:
        """Get the subnet's pool info."""
        if not self.pool_hotkey:
            self.pool_hotkey = self.get_owner_hotkey()

        if self.pool_hotkey is None:
            logging.error("Cannot get subnet pool - pool hotkey not found")
            return None

        try:
            pool_info = get_pool_info(self.subtensor, self.config.netuid, self.pool_hotkey)

            if pool_info:
                logging.info(
                    f"Retrieved subnet's pool info: "
                    f"pool_index={pool_info.pool_index}, "
                    f"domain={pool_info.domain}, "
                    f"port={pool_info.port}"
                )
            else:
                logging.warning(
                    f"No pool info found for subnet (hotkey: {self.pool_hotkey})"
                )

            return pool_info
        except Exception as e:
            logging.error(f"Error getting subnet's pool info: {e}")
            return None
