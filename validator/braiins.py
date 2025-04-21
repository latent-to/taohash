#! /usr/bin/env python3

# Copyright © 2025 Latent Holdings
# Licensed under GPLv3

from typing import List, Optional

import os
import argparse
import traceback
import bittensor as bt
from bittensor_wallet.bittensor_wallet import Wallet

from taohash.pool import Pool, PoolBase
from taohash.pool.metrics import get_metrics_for_miners, MiningMetrics
from taohash.pricing import CoinPriceAPI, CoinPriceAPIBase, BraiinsHashPriceAPI
from taohash.chain_data.chain_data import (
    publish_pool_info,
    get_pool_info,
    encode_pool_info,
)

from taohash.pool.braiins.config import BraiinsPoolAPIConfig, BraiinsPoolConfig

from validator import BaseValidator

COIN = "bitcoin"


class BraiinsValidator(BaseValidator):
    def __init__(self):
        self.config = self.get_config()
        self.setup_logging()

        self.pool_config = BraiinsPoolConfig.from_args(self.config)
        self.api_config = BraiinsPoolAPIConfig.from_args(self.config)
        self.pool = Pool(
            pool_info=self.pool_config.to_pool_info(), config=self.api_config
        )
        self.price_api: CoinPriceAPIBase = CoinPriceAPI(
            method=self.config.price.method, api_key=self.config.price.api_key
        )
        self.hash_price_api: BraiinsHashPriceAPI = BraiinsHashPriceAPI()

        self.setup_bittensor_objects()
        self.last_update = 0
        self.uid = self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address)
        self.scores = [0.0] * len(self.metagraph.S)
        self.current_block = 0
        self.tempo = self.subtensor.tempo(self.config.netuid)
        self.moving_avg_scores = [0.0] * len(self.metagraph.S)
        self.alpha = 0.1
        self.sync_interval_blocks = 25  # Every 5 minutes

    def get_config(self):
        # Set up the configuration parser.
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
                config.wallet.hotkey_str,
                config.netuid,
                "validator",
            )
        )
        # Ensure the logging directory exists.
        os.makedirs(config.full_path, exist_ok=True)

        # TODO: support multiple coins
        config.coins = [COIN]

        return config

    def setup_logging(self):
        # Set up logging.
        bt.logging(config=self.config, logging_dir=self.config.full_path)
        bt.logging.info(
            f"Running validator for subnet: {self.config.netuid} on network: {self.config.subtensor.network} with config:\n{self.config}"
        )
        bt.logging.set_info()

    def setup_bittensor_objects(self):
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
            self.my_subnet_uid = self.metagraph.hotkeys.index(
                self.wallet.hotkey.ss58_address
            )
            bt.logging.info(f"Running validator on uid: {self.my_subnet_uid}")

        # Set up initial scoring weights for validation.
        bt.logging.info("Building validation weights.")
        self.scores = [0.0] * len(self.metagraph.S)
        bt.logging.info(f"Weights: {self.scores}")

        # Publish Validator's pool info to the chain.
        self._publish_pool_info(
            self.subtensor, self.config.netuid, self.wallet, self.pool
        )

    def _get_pool_info_bytes(
        self, node: "bt.subtensor", netuid: int, wallet: "Wallet"
    ) -> bytes:
        pool_info = get_pool_info(node, netuid, wallet.hotkey.ss58_address)
        if pool_info is None:
            return None
        return encode_pool_info(pool_info)

    def _publish_pool_info(
        self, node: "bt.subtensor", netuid: int, wallet: "Wallet", pool: PoolBase
    ) -> None:
        bt.logging.info(f"Publishing pool info to netuid: {netuid}")

        bt.logging.info("Checking if pool info is already published.")
        pool_info = pool.get_pool_info()
        pool_info_bytes = encode_pool_info(pool_info)

        curr_pool_info_bytes = self._get_pool_info_bytes(node, netuid, wallet)

        if curr_pool_info_bytes is not None:
            bt.logging.info("Pool info detected.")
            if curr_pool_info_bytes == pool_info_bytes:
                bt.logging.success("Pool info is already published.")
                return
            else:
                bt.logging.info("Pool info is outdated.")

        bt.logging.info("Publishing pool info to the chain.")
        # Publish the pool info to the chain.
        success = publish_pool_info(node, netuid, wallet, pool_info_bytes)
        if not success:
            bt.logging.error("Failed to publish pool info")
            exit(1)
        else:
            bt.logging.success("Pool info published successfully")

    def node_query(self, module, method, params):
        result = self.subtensor.query_module(module=module, name=method, params=params)
        if method == "SubnetOwnerHotkey":
            return result
        return result.value

    def evaluate_miner_hashrate(self):
        hotkey_to_uid = {n.hotkey: n.uid for n in self.metagraph.neurons}
        for coin in self.config.coins:
            miner_metrics: List[MiningMetrics] = get_metrics_for_miners(
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
            bt.logging.info(f"Current scores: {self.scores}")

    def set_weights(self):
        for i, current_score in enumerate(self.scores):
            self.moving_avg_scores[i] = (1 - self.alpha) * self.moving_avg_scores[
                i
            ] + self.alpha * current_score

        bt.logging.info(f"Moving Average Scores: {self.moving_avg_scores}")

        # Calculate weights
        total = sum(self.moving_avg_scores)
        if total == 0:
            bt.logging.info("No miners are mining, we should burn the alpha")
            # No miners are mining, we should burn the alpha
            owner_hotkey = self.node_query(
                "SubtensorModule", "SubnetOwnerHotkey", [self.config.netuid]
            )
            owner_uid = self.metagraph.hotkeys.index(owner_hotkey)
            if owner_uid is not None:
                weights = [0.0] * len(self.metagraph.S)
                weights[owner_uid] = 1.0
            else:
                bt.logging.error("No owner found for subnet. Skipping weight update.")
                return False, "No owner found for the subnet"
        else:
            weights = [score / total for score in self.moving_avg_scores]

        bt.logging.info(f"Setting weights: {weights}")

        # Update the incentive mechanism on the Bittensor blockchain.
        success, err_msg = self.subtensor.set_weights(
            netuid=self.config.netuid,
            wallet=self.wallet,
            uids=self.metagraph.uids,
            weights=weights,
            wait_for_inclusion=True,
        )
        if success:
            self.last_update = self.current_block
            # Reset scores for next evaluation
            self.scores = [0.0] * len(self.metagraph.S)
            return True, err_msg
        return False, err_msg

    def run(self):
        # The Main Validation Loop.
        bt.logging.info("Starting validator loop.")

        self.metagraph.sync()
        self.current_block = self.metagraph.block.item()
        bt.logging.info(f"Performed initial sync at block {self.current_block}")

        next_sync_block = self.current_block + self.sync_interval_blocks
        bt.logging.info(f"Next sync at block: {next_sync_block}")

        while True:
            try:
                if self.subtensor.wait_for_block(next_sync_block):
                    self.metagraph.sync()
                    self.current_block = self.metagraph.block.item()
                    blocks_since_last_weights = self.subtensor.blocks_since_last_update(
                        self.config.netuid, self.my_subnet_uid
                    )

                    self.evaluate_miner_hashrate()

                    if blocks_since_last_weights >= self.tempo:
                        bt.logging.info(
                            f"Setting weights: {blocks_since_last_weights} >= {self.tempo}"
                        )
                        success, err_msg = self.set_weights()
                        if not success:
                            bt.logging.error(f"Failed to set weights: {err_msg}")
                            continue

                    # Calculate next sync block
                    next_sync_block = self.current_block + self.sync_interval_blocks
                    blocks_until_next_weights = self.tempo - blocks_since_last_weights
                    next_weights_str = (
                        "Setting weights in next sync"
                        if blocks_until_next_weights < 0
                        else f"Next set_weights: {blocks_until_next_weights}"
                    )

                    bt.logging.info(
                        f"Block: {self.current_block} | "
                        f"Next sync: {next_sync_block} | "
                        f"VTrust: {self.metagraph.validator_trust[self.my_subnet_uid]} | "
                        f"{next_weights_str}"
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
    validator = BraiinsValidator()
    validator.run()
