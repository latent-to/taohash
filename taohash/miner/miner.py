import json
import os
import argparse
import traceback
from pathlib import Path
from typing import Dict, List, Tuple

import bittensor as bt

from taohash.chain_data.chain_data import get_pool_info


JSON_BASE_PATH = "~/.bittensor/data/pools"
BLOCKS_PER_EPOCH = 360
DEFAULT_SYNC_FREQUENCY = 6


class Miner:
    def __init__(self):
        """Initialize the miner with configuration and setup."""
        self.config = self.get_config()
        self.setup_logging()
        self.setup_bittensor_objects()

    def get_config(self):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--netuid", type=int, default=1, help="The chain subnet uid."
        )
        # Json path to save the pool configuration
        parser.add_argument(
            "--json_path",
            type=str,
            help=f"Path to save the pool configuration JSON file. If not provided, will use {JSON_BASE_PATH}.",
        )
        # Sync frequency
        parser.add_argument(
            "--sync_frequency",
            type=int,
            default=DEFAULT_SYNC_FREQUENCY,
            choices=range(1, 360),
            help=f"Number of times to sync and update pool info per epoch (1-359). Default is {DEFAULT_SYNC_FREQUENCY} times per epoch.",
        )

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

        # Default JSON path
        if not hasattr(config, "json_path") or not config.json_path:
            config.json_path = os.path.expanduser(JSON_BASE_PATH)

        return config

    def setup_logging(self) -> None:
        """Set up logging for the miner."""
        bt.logging(config=self.config, logging_dir=self.config.full_path)
        bt.logging.set_info()
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
        bt.logging.info(f"Running miner on uid: {self.my_subnet_uid}")

    def get_sorted_validators(self) -> List[Tuple[int, float]]:
        """Fetch and sort validators by stake."""
        # TODO:Should we also add condition of min 10k stake weight?
        max_validators = self.subtensor.substrate.query(
            module="SubtensorModule",
            storage_function="MaxAllowedValidators",
            params=[self.config.netuid],
        ).value

        sorted_by_stake = sorted(
            [(n.uid, n.stake) for n in self.metagraph.neurons],
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_by_stake[:max_validators]

    def get_pool_mapping(self, validators: List[Tuple[int, float]]) -> Dict:
        """Create a mapping of validator pool information."""
        # Calculate total stake across all validators
        stake_sum = sum(
            [self.metagraph.neurons[uid].total_stake for uid, _ in validators]
        )

        pool_mapping = {}
        for uid, _ in validators:
            validator_hotkey = self.metagraph.hotkeys[uid]
            pool_info = get_pool_info(
                self.subtensor, self.config.netuid, validator_hotkey
            )
            total_stake = self.metagraph.neurons[uid].total_stake

            if pool_info is not None:
                normalized_weight = total_stake.tao / stake_sum.tao
                pool_mapping[validator_hotkey] = {
                    "pool_info": pool_info.to_json(),
                    "pool_weight": normalized_weight,
                    "uid": uid,
                    "total_stake": total_stake.tao,
                    "stake_percentage": normalized_weight * 100,
                }
            else:
                bt.logging.debug(
                    f"Skipping validator {uid} ({validator_hotkey}) - no pool information available"
                )

        return pool_mapping

    def save_pool_data(self, pool_mapping: Dict) -> None:
        """Save pool data to a JSON file."""
        pools_dir = Path(self.config.json_path)
        pools_dir.mkdir(parents=True, exist_ok=True)

        current_block = self.metagraph.block.item()
        pool_data_file = pools_dir / f"{current_block}-pools.json"

        with open(pool_data_file, "w") as f:
            json.dump(pool_mapping, f, indent=4)
        bt.logging.info(f"Updated pool data saved to {pool_data_file}")

    def run(self) -> None:
        """Run the main miner loop."""
        bt.logging.info("Starting main loop")

        # Calculate blocks between syncs
        blocks_between_syncs = BLOCKS_PER_EPOCH // self.config.sync_frequency

        # Calculate next sync block
        self.metagraph.sync()
        current_block = self.metagraph.block.item()
        next_sync_block = current_block + (
            blocks_between_syncs - (current_block % blocks_between_syncs)
        )

        while True:
            try:
                # Wait for the next sync block
                if self.subtensor.wait_for_block(next_sync_block):
                    self.metagraph.sync()
                    current_block = self.metagraph.block.item()

                    bt.logging.info(f"Collecting pool info at block {current_block}")
                    validators = self.get_sorted_validators()
                    pool_mapping = self.get_pool_mapping(validators)
                    self.save_pool_data(pool_mapping)

                    next_sync_block = current_block + blocks_between_syncs

                    log = (
                        f"Block: {current_block} | "
                        f"Incentive: {self.metagraph.I[self.my_subnet_uid]} | "
                        f"Blocks since epoch: {self.metagraph.blocks_since_last_step} | "
                        f"Next sync at block: {next_sync_block}"
                    )
                    bt.logging.info(log)
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
