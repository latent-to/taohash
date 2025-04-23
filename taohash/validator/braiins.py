#! /usr/bin/env python3

# Copyright © 2025 Latent Holdings
# Licensed under GPLv3

import os
import argparse
import traceback
import bittensor as bt
from dotenv import load_dotenv

from bittensor_wallet.bittensor_wallet import Wallet

from taohash.core.pool import Pool, PoolBase
from taohash.core.pool.metrics import get_metrics_for_miners, MiningMetrics
from taohash.core.pricing import BraiinsHashPriceAPI
from taohash.core.chain_data.pool_info import (
    publish_pool_info,
    get_pool_info,
    encode_pool_info,
)
from taohash.core.constants import BLOCK_TIME
from taohash.core.pool.braiins.config import BraiinsPoolAPIConfig, BraiinsPoolConfig
from taohash.validator import BaseValidator

COIN = "bitcoin"


class BraiinsValidator(BaseValidator):
    def __init__(self):
        # Base validator initialization
        super().__init__()
        self.config = self.get_config()
        self.setup_logging()

        self.pool_config = BraiinsPoolConfig.from_args(self.config)
        self.api_config = BraiinsPoolAPIConfig.from_args(self.config)
        self.pool = Pool(
            pool_info=self.pool_config.to_pool_info(), config=self.api_config
        )
        self.hash_price_api: BraiinsHashPriceAPI = BraiinsHashPriceAPI()
        self.setup_bittensor_objects()
        self.scores = [0.0] * len(self.metagraph.S)
        self.current_block = 0
        self.tempo = self.subtensor.tempo(self.config.netuid)
        self.moving_avg_scores = [0.0] * len(self.metagraph.S)
        self.alpha = 0.8
        self.sync_interval_blocks = 25  # Every 5 minutes

    def get_config(self):
        """
        Set up the configuration parser.
        """
        parser = argparse.ArgumentParser(
            description="TAOHash (Braiins) Validator",
            usage="python3 validator/braiins.py <command> [options]",
            add_help=True,
        )
        command_parser = parser.add_subparsers(dest="command")
        run_command_parser = command_parser.add_parser(
            "run", help="""Run the validator"""
        )

        BraiinsPoolConfig.add_args(run_command_parser)
        BraiinsPoolAPIConfig.add_args(run_command_parser)

        # Add the base validator arguments.
        super().add_args(run_command_parser)

        # Parse the config.
        try:
            config = bt.config(parser)
        except ValueError as e:
            print(f"Error parsing config: {e}")
            exit(1)
        # Set up logging directory.
        config.full_path = os.path.expanduser(
            "{}/{}/{}/netuid{}/{}".format(
                config.logging.logging_dir,
                config.wallet.name,
                config.wallet.hotkey,
                config.netuid,
                "validator",
            )
        )
        # Ensure the logging directory exists.
        os.makedirs(config.full_path, exist_ok=True)

        # TODO: support multiple coins
        config.coins = [COIN]

        return config

    def setup_bittensor_objects(self):
        """
        Setup Bittensor objects.
        1. Initialize wallet.
        2. Initialize subtensor.
        3. Initialize metagraph.
        4. Ensure validator is registered to the network.
        5. Set up initial scoring weights for validation.
        6. Publish validator's pool info to the chain.
        """
        # Build Bittensor validator objects.
        bt.logging.info("Setting up Bittensor objects.")

        # Initialize wallet.
        self.wallet = Wallet(config=self.config)
        bt.logging.info(f"Wallet: {self.wallet}")

        # Initialize subtensor.
        self.subtensor = bt.subtensor(config=self.config)
        bt.logging.info(f"Subtensor: {self.subtensor}")

        # Initialize metagraph.
        self.metagraph = self.subtensor.metagraph(self.config.netuid)
        bt.logging.info(f"Metagraph: {self.metagraph}")

        # Connect the validator to the network.
        if self.wallet.hotkey.ss58_address not in self.metagraph.hotkeys:
            bt.logging.error(
                f"\nYour validator: {self.wallet} is not registered to chain connection: {self.subtensor} \nRun 'btcli register' and try again."
            )
            exit()
        else:
            # Each validator gets a unique identity (UID) in the network.
            self.uid = self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address)
            bt.logging.info(f"Running validator on uid: {self.uid}")

        # Set up initial scoring weights for validation.
        bt.logging.info("Building validation weights.")
        self.scores = [0.0] * len(self.metagraph.S)
        bt.logging.info(f"Weights: {self.scores}")

        # Publish Validator's pool info to the chain.
        self.publish_pool_info(
            self.subtensor, self.config.netuid, self.wallet, self.pool
        )

    def publish_pool_info(
        self, subtensor: "bt.subtensor", netuid: int, wallet: "Wallet", pool: PoolBase
    ) -> None:
        """
        Publish the pool info to the chain.
        Process:
            1. Check if pool info is already published.
            2. If not, publish the pool info to the chain.
            3. Update the pool info if it is outdated.
        """
        pool_info = pool.get_pool_info()
        pool_info_bytes = encode_pool_info(pool_info)

        _curr_pool_info_bytes = get_pool_info(subtensor, netuid, wallet.hotkey.ss58_address)
        if _curr_pool_info_bytes is not None:
            bt.logging.info("Pool info detected.")
            curr_pool_info_bytes = encode_pool_info(_curr_pool_info_bytes)
            if curr_pool_info_bytes == pool_info_bytes:
                bt.logging.success("Pool info is already published.")
                return
            else:
                bt.logging.info("Pool info is outdated.")

        bt.logging.info("Publishing pool info to the chain.")
        success = publish_pool_info(subtensor, netuid, wallet, pool_info_bytes)
        if not success:
            bt.logging.error("Failed to publish pool info")
            exit(1)
        else:
            bt.logging.success("Pool info published successfully")

    def get_next_sync_block(self) -> tuple[int, str]:
        """
        Calculate the next block to sync at.
        Returns:
            tuple[int, str]: (next_block, sync_reason)
            - next_block: the block number to sync at
            - sync_reason: reason for the sync ("Regular sync" or "Weights due")
        """
        sync_reason = "Regular sync"
        next_sync = self.current_block + self.sync_interval_blocks

        blocks_since_last_weights = self.subtensor.blocks_since_last_update(
            self.config.netuid, self.uid
        )
        # Calculate when we'll need to set weights
        blocks_until_weights = self.tempo - blocks_since_last_weights
        next_weights_block = self.current_block + blocks_until_weights + 1

        if blocks_since_last_weights >= self.tempo:
            sync_reason = "Weights due"
            return self.current_block + 1, sync_reason

        elif next_weights_block <= next_sync:
            sync_reason = "Weights due"
            return next_weights_block, sync_reason

        return next_sync, sync_reason

    def evaluate_miner_hashrate(self):
        """
        Evaluate value provided by miners.
        Process:
            1. Fetch miner metrics (API fetches hashrate for the last 5m).
            2. Fetch hash price for the coin (USD/TH/day).
            3. Calculate value provided in the past 5m
            4. Update scores for each miner.
        """
        hotkey_to_uid = {n.hotkey: n.uid for n in self.metagraph.neurons}
        for coin in self.config.coins:
            miner_metrics: list[MiningMetrics] = get_metrics_for_miners(
                self.pool, self.metagraph.neurons, coin
            )
            hash_price = self.hash_price_api.get_hash_price(coin)
            if hash_price is None:
                # If we can't grab the price, don't count the shares
                continue

            for metric in miner_metrics:
                uid = hotkey_to_uid[metric.hotkey]
                mining_value: float = metric.get_value_last_5m(hash_price)
                self.scores[uid] += mining_value
            self._log_scores(coin, hash_price)

    def get_burn_uid(self):
        """
        Get the UID of the subnet owner.
        """
        sn_owner_hotkey = self.subtensor.query_subtensor(
            "SubnetOwnerHotkey",
            params=[self.config.netuid],
        )
        owner_uid = self.metagraph.hotkeys.index(sn_owner_hotkey)
        return owner_uid

    def ensure_validator_permit(self):
        """
        Ensure the validator has a permit to participate in the network.
        If not, wait for the next step.
        """
        validator_permits = self.subtensor.query_subtensor(
            "ValidatorPermit",
            params=[self.config.netuid],
        ).value
        if not validator_permits[self.uid]:
            blocks_since_last_step = self.subtensor.query_subtensor(
                "BlocksSinceLastStep",
                block=self.current_block,
                params=[self.config.netuid],
            ).value
            time_to_wait = (self.tempo - blocks_since_last_step) * BLOCK_TIME + 0.1
            bt.logging.error(
                f"Validator permit not found. Waiting {time_to_wait} seconds."
            )
            target_block = self.current_block + (self.tempo - blocks_since_last_step)
            self.subtensor.wait_for_block(target_block)

    def set_weights(self):
        """
        Set the weights for all miners once per tempo.
        Process:
            1. Update moving average scores from base scores.
            2. Ensure miners are still active - otherwise burn the alpha.
            3. Set weights using moving average scores.
            4. Reset scores for next evaluation.
        """
        # Update moving average scores from base scores.
        for i, current_score in enumerate(self.scores):
            self.moving_avg_scores[i] = (1 - self.alpha) * self.moving_avg_scores[
                i
            ] + self.alpha * current_score

        # Calculate weights
        total = sum(self.moving_avg_scores)
        if total == 0:
            bt.logging.info("No miners are mining, we should burn the alpha")
            # No miners are mining, we should burn the alpha
            owner_uid = self.get_burn_uid()
            if owner_uid is not None:
                weights = [0.0] * len(self.metagraph.S)
                weights[owner_uid] = 1.0
            else:
                bt.logging.error("No owner found for subnet. Skipping weight update.")
                return False, "No owner found for the subnet"
        else:
            weights = [score / total for score in self.moving_avg_scores]

        bt.logging.info("Setting weights")
        # Update the incentive mechanism on the Bittensor blockchain.
        success, err_msg = self.subtensor.set_weights(
            netuid=self.config.netuid,
            wallet=self.wallet,
            uids=self.metagraph.uids,
            weights=weights,
            wait_for_inclusion=True,
            period=15,
        )
        if success:
            self._log_weights_and_scores(weights)
            self.last_update = self.current_block
            # Reset scores for next evaluation
            self.scores = [0.0] * len(self.metagraph.S)
            return True, err_msg
        return False, err_msg

    def run(self):
        """
        The Main Validation Loop.
        Process:
            1. Sync the metagraph.
            2. Ensure the validator has a permit.
            3. Sync on every `sync_interval_blocks` (25 blocks) to:
                - Sync the metagraph.
                - Evaluate miner hashrate.
                - Set weights for all miners once per tempo.
        """
        bt.logging.info("Starting validator loop.")

        self.metagraph.sync()
        self.current_block = self.metagraph.block.item()
        bt.logging.info(f"Performed initial sync at block {self.current_block}")

        self.ensure_validator_permit()

        next_sync_block = self.current_block + self.sync_interval_blocks
        bt.logging.info(f"Next sync at block {next_sync_block}")

        while True:
            try:
                if self.subtensor.wait_for_block(next_sync_block):
                    self.resync_metagraph()
                    self.current_block = self.metagraph.block.item()
                    blocks_since_last_weights = self.subtensor.blocks_since_last_update(
                        self.config.netuid, self.uid
                    )

                    self.evaluate_miner_hashrate()

                    if blocks_since_last_weights >= self.tempo:
                        success, err_msg = self.set_weights()
                        if not success:
                            bt.logging.error(f"Failed to set weights: {err_msg}")
                            continue

                    next_sync_block, sync_reason = self.get_next_sync_block()
                    bt.logging.info(
                        f"Block: {self.current_block} | "
                        f"Next sync: {next_sync_block} | "
                        f"Sync reason: {sync_reason} | "
                        f"VTrust: {self.metagraph.validator_trust[self.uid]}"
                    )
                else:
                    bt.logging.warning("Timeout waiting for block, retrying...")
                    continue

            except RuntimeError as e:
                bt.logging.error(e)
                traceback.print_exc()

            except KeyboardInterrupt:
                bt.logging.success("Keyboard interrupt detected. Exiting validator.")
                exit()


# Run the validator.
if __name__ == "__main__":
    load_dotenv()
    validator = BraiinsValidator()
    validator.run()
