#! /usr/bin/env python3

# Copyright © 2025 Latent Holdings
# Licensed under MIT

import argparse
import traceback

from bittensor import logging, Subtensor
from bittensor_wallet.bittensor_wallet import Wallet
from dotenv import load_dotenv

from taohash.core.chain_data.pool_info import (
    publish_pool_info,
    get_pool_info,
    encode_pool_info,
)
from taohash.core.pool import Pool, PoolBase
from taohash.core.pool.braiins.config import BraiinsPoolAPIConfig, BraiinsPoolConfig
from taohash.core.pool.metrics import get_metrics_for_miners, MiningMetrics
from taohash.core.pricing import BraiinsHashPriceAPI, HashPriceAPIBase
from taohash.core.constants import VERSION_KEY
from taohash.validator import BaseValidator

COIN = "bitcoin"


class BraiinsValidator(BaseValidator):
    """
    Braiins BTC Validator.
    """

    def __init__(self):
        # Base validator initialization
        super().__init__()

        self.setup_bittensor_objects()
        self.primary_pool_hotkey = self.get_primary_pool_hotkey()

        if self.wallet.hotkey.ss58_address == self.primary_pool_hotkey:
            self.config.pool.use_primary_api = False

        self.setup_pool_objects()

        self.hash_price_api: "HashPriceAPIBase" = BraiinsHashPriceAPI()
        self.alpha = 0.8
        self.weights_interval = self.tempo # 360 blocks
        self.config.coins = [COIN]

    def add_args(self, parser: argparse.ArgumentParser):
        """Add Braiins-specific arguments to the parser."""
        super().add_args(parser)
        BraiinsPoolConfig.add_args(parser)
        BraiinsPoolAPIConfig.add_args(parser)

    def setup_pool_objects(self):
        """
        Setup the pool objects for Braiins BTC Pool.
        """
        self.api_config = BraiinsPoolAPIConfig.from_args(self.config, wallet=self.wallet)
        if not self.config.pool.use_primary_api:
            self.pool_config = BraiinsPoolConfig.from_args(self.config)
            self.pool = Pool(
                pool_info=self.pool_config.to_pool_info(), config=self.api_config
            )
            self.publish_pool_info(
                self.subtensor, self.config.netuid, self.wallet, self.pool
            )
        else:
            pool_info = get_pool_info(
                self.subtensor, self.config.netuid, self.primary_pool_hotkey
            )
            if not pool_info:
                logging.error(
                    f"No pool info found for primary pool: {self.primary_pool_hotkey}"
                )
                exit(1)
            self.pool = Pool(pool_info=pool_info, config=self.api_config)

    def publish_pool_info(
        self, subtensor: "Subtensor", netuid: int, wallet: "Wallet", pool: PoolBase
    ) -> None:
        """
        Publish the mining pool info to bittensor.
        Process:
            1. Check if pool info is already published.
            2. If not, publish the pool info to the chain.
            3. Update the pool info if it is outdated.
        """
        pool_info = pool.get_pool_info()
        pool_info_bytes = encode_pool_info(pool_info)

        published_pool_info = get_pool_info(
            subtensor, netuid, wallet.hotkey.ss58_address
        )
        if published_pool_info is not None:
            logging.info("Pool info detected.")
            published_pool_info_bytes = encode_pool_info(published_pool_info)
            if published_pool_info_bytes == pool_info_bytes:
                logging.success("Pool info is already published.")
                return
            else:
                logging.info("Pool info is outdated.")

        logging.info("Publishing pool info to the chain.")
        success = publish_pool_info(subtensor, netuid, wallet, pool_info_bytes)
        if not success:
            logging.error("Failed to publish pool info")
            exit(1)
        else:
            logging.success("Pool info published successfully")

    def evaluate_miner_hashrate(self, timeframe: str = "5m") -> None:
        """
        Evaluate value provided by miners.

        Args:
            timeframe: The timeframe to evaluate ("5m" for 5 minutes or "60m" for 60 minutes)

        Evaluation:
            1. Fetch miner metrics (API fetches hashrate for the last 5m or 60m).
            2. Fetch hash price for the coin (USD/TH/day).
            3. Calculate value provided in the specified timeframe
            4. Update scores for each miner.
        """
        hotkey_to_uid = {hotkey: uid for uid, hotkey in enumerate(self.hotkeys)}
        for coin in self.config.coins:
            miner_metrics: list[MiningMetrics] = get_metrics_for_miners(
                self.pool, self.hotkeys, coin
            )
            hash_price = self.hash_price_api.get_hash_price(coin)
            if hash_price is None:
                # If we can't grab the price, don't count the shares
                logging.error(f"Failed to get hash price for coin: {coin}")
                continue

            for metric in miner_metrics:
                uid = hotkey_to_uid[metric.hotkey]
                if timeframe == "5m":
                    mining_value: float = metric.get_value_last_5m(hash_price)
                else:  # "60m"
                    mining_value: float = metric.get_value_past_hour(hash_price)

                if mining_value > 0:
                    logging.info(
                        f"Mining value ({timeframe}): {mining_value}, hotkey: {metric.hotkey}, uid: {uid}"
                    )
                self.scores[uid] += mining_value
            self._log_scores(coin, hash_price)

    def restore_state_and_evaluate(self) -> None:
        """
        Braiins specific: Attempt to restore validator state from storage.
        Handles different recovery scenarios based on how long the validator was down.

        Process:
            1. No previous state: start fresh.
            2. Down >= 1.5 hours: start fresh.
            3. Down >= 1 hour: evaluate last hour's scores.
            4. Down < 1 hour: restore the state.
        """
        state = self.storage.load_latest_state()
        if state is None:
            logging.info("No previous state found, starting fresh")
            return

        blocks_down = self.current_block - state["current_block"]
        if blocks_down >= (self.tempo * 1.5):
            logging.warning(
                f"Validator was down for {blocks_down} blocks (> {self.tempo * 1.5}). Starting fresh."
            )
            return

        # Restore state
        total_hotkeys = len(state.get("hotkeys", []))
        self.scores = state.get("scores", [0.0] * total_hotkeys)
        self.moving_avg_scores = state.get("moving_avg_scores", [0.0] * total_hotkeys)
        self.hotkeys = state.get("hotkeys", [])
        self.resync_metagraph()

        if blocks_down > 230:  # 1 hour
            logging.warning(
                f"Validator was down for {blocks_down} blocks (> 230). Will fetch last hour's scores."
            )
            self.evaluate_miner_hashrate(timeframe="60m")
        logging.success("Successfully restored validator state")

    def set_weights(self) -> tuple[bool, str]:
        """Set weights for all miners.

        Returns:
            tuple[bool, str]: A tuple containing:
                - bool: True if weights were set successfully, False otherwise
                - str: Error message if weights were not set successfully, empty string otherwise

        Evaluation:
            1. Update moving_avg_scores from base scores.
            2. Ensure miners are still active - otherwise burn the alpha.
            3. Set weights using moving_avg_scores.
            4. Reset scores for next evaluation.
        """
        # Update moving_avg_scores from base scores.
        for i, current_score in enumerate(self.scores):
            self.moving_avg_scores[i] = (1 - self.alpha) * self.moving_avg_scores[
                i
            ] + self.alpha * current_score

        # Calculate weights
        total = sum(self.moving_avg_scores)
        if total == 0:
            logging.info("No miners are mining, we should burn the alpha")
            # No miners are mining, we should burn the alpha
            owner_uid = self.get_burn_uid()
            if owner_uid is not None:
                weights = [0.0] * len(self.hotkeys)
                weights[owner_uid] = 1.0
            else:
                logging.error("No owner found for subnet. Skipping weight update.")
                return False, "No owner found for the subnet"
        else:
            weights = [score / total for score in self.moving_avg_scores]

        logging.info("Setting weights")
        # Update the incentive mechanism on the Bittensor blockchain.
        success, err_msg = self.subtensor.set_weights(
            netuid=self.config.netuid,
            wallet=self.wallet,
            uids=self.metagraph.uids,
            weights=weights,
            wait_for_inclusion=True,
            version_key=VERSION_KEY,
        )
        if success:
            self._log_weights_and_scores(weights)
            self.last_update = self.current_block
            # Reset base scores for next evaluation
            self.scores = [0.0] * len(self.hotkeys)
            return True, err_msg
        return False, err_msg

    def run(self):
        """
        The Main Validation Loop.

        Process:
            1. Restore state and/or resync metagraph.
            2. Ensure the validator has a permit.
            3. Sync on every `sync_interval_blocks` (25 blocks) to:
                - Sync the metagraph.
                - Evaluate miner hashrate.
                - Set weights for all miners once per `weights_interval`.
        """
        if self.config.state == "restore":
            self.restore_state_and_evaluate()
        else:
            self.resync_metagraph()

        logging.info(f"Starting validator loop, current block: {self.current_block}")

        self.ensure_validator_permit()

        next_sync_block = self.current_block + self.eval_interval
        logging.info(f"Next sync at block {next_sync_block}")

        while True:
            try:
                if self.subtensor.wait_for_block(next_sync_block):
                    self.resync_metagraph()
                    self.evaluate_miner_hashrate(timeframe="5m")

                    blocks_since_last_weights = self.subtensor.blocks_since_last_update(
                        self.config.netuid, self.uid
                    )
                    if blocks_since_last_weights >= self.weights_interval:
                        success, err_msg = self.set_weights()
                        if not success:
                            logging.error(f"Failed to set weights: {err_msg}")
                            continue

                    self.save_state()
                    next_sync_block, sync_reason = self.get_next_sync_block()
                    logging.info(
                        f"Block: {self.current_block} | "
                        f"Next sync: {next_sync_block} | "
                        f"Sync reason: {sync_reason} | "
                        f"VTrust: {self.metagraph.validator_trust[self.uid]}"
                    )
                else:
                    logging.warning("Timeout waiting for block, retrying...")
                    continue

            except RuntimeError as e:
                logging.error(e)
                traceback.print_exc()

            except KeyboardInterrupt:
                logging.success("Keyboard interrupt detected. Exiting validator.")
                exit()


# Run the validator.
if __name__ == "__main__":
    load_dotenv()
    validator = BraiinsValidator()
    validator.run()
