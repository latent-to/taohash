#! /usr/bin/env python3

# Copyright © 2025 Latent Holdings
# Licensed under MIT

import argparse
import traceback
import time

from bittensor import logging, Subtensor
from bittensor_wallet.bittensor_wallet import Wallet
from dotenv import load_dotenv

from taohash.core.chain_data.pool_info import (
    publish_pool_info,
    get_pool_info,
    encode_pool_info,
)
from taohash.core.constants import VERSION_KEY, U16_MAX
from taohash.core.pool import Pool, PoolBase
from taohash.core.pool.metrics import ProxyMetrics, get_metrics_timerange
from taohash.core.pool.proxy.config import ProxyPoolAPIConfig, ProxyPoolConfig
from taohash.core.pricing import CoinPriceAPI
from taohash.validator import BaseValidator

COIN = "bitcoin"

BAD_COLDKEYS = ["5CS96ckqKnd2snQ4rQKAvUpMh2pikRmCHb4H7TDzEt2AM9ZB"]


class TaohashProxyValidator(BaseValidator):
    """
    Taohash Proxy BTC Validator.

    This validator uses the Taohash proxy to retrieve miner statistics
    instead of directly querying the Braiins pool API.
    """

    def __init__(self):
        super().__init__()

        self.pool_config = ProxyPoolConfig.from_args(self.config)
        self.api_config = ProxyPoolAPIConfig.from_args(self.config)
        self.pool = Pool(
            pool_info=self.pool_config.to_pool_info(), config=self.api_config
        )
        self.setup_bittensor_objects()
        self.price_api = CoinPriceAPI("coingecko", None)

        self.alpha = 0.8
        self.weights_interval = self.tempo * 2
        self.config.coins = [COIN]

        self.last_evaluation_timestamp = None

    def add_args(self, parser: argparse.ArgumentParser):
        """Add proxy-specific arguments to the parser."""
        super().add_args(parser)
        ProxyPoolConfig.add_args(parser)
        ProxyPoolAPIConfig.add_args(parser)

    def setup_bittensor_objects(self):
        """
        Extend base setup with proxy-specific setup.
        """
        super().setup_bittensor_objects()
        self.publish_pool_info(
            self.subtensor, self.config.netuid, self.wallet, self.pool
        )

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

    def evaluate_miner_share_value(self) -> None:
        """
        Evaluate value provided by miners based on share values for a time range.

        Evaluation:
            1. Determine time range (last 10 minutes for first run, or since last evaluation)
            2. Fetch miner contributions from proxy for that time range
            3. Update scores for each miner based on share values
        """
        hotkey_to_uid = {hotkey: uid for uid, hotkey in enumerate(self.hotkeys)}

        current_time = int(time.time())

        if self.last_evaluation_timestamp:
            start_time = self.last_evaluation_timestamp
            end_time = current_time

            max_range = 24 * 60 * 60
            if end_time - start_time > max_range:
                start_time = end_time - max_range

            logging.info(
                f"Evaluating miners for time range: {start_time} to {end_time} ({end_time - start_time} seconds)"
            )
        else:
            # First evaluation - use last 10 minutes
            end_time = current_time
            start_time = end_time - (10 * 60)
            logging.info(
                f"First evaluation - using last 10 minutes: {start_time} to {end_time}"
            )

        for coin in self.config.coins:
            miner_metrics: list[ProxyMetrics] = get_metrics_timerange(
                self.pool,
                self.hotkeys,
                self.block_at_registration,
                start_time,
                end_time,
                coin,
            )

            for metric in miner_metrics:
                if metric.hotkey not in hotkey_to_uid:
                    continue

                uid = hotkey_to_uid[metric.hotkey]
                btc_price = self.price_api.get_price(coin)
                share_value = metric.get_share_value(btc_price)

                if share_value > 0:
                    logging.info(
                        f"Share value: {share_value}, hotkey: {metric.hotkey}, uid: {uid}"
                    )

                self.scores[uid] += share_value

            self._log_share_value_scores(coin, f"{end_time - start_time}s")

        self.last_evaluation_timestamp = current_time
        logging.info(f"Updated last_evaluation_timestamp to {current_time}")

    def _log_share_value_scores(self, coin: str, timeframe: str) -> None:
        """Log current scores based on share values."""
        rows = []
        headers = ["UID", "Hotkey", "Score", "Moving Avg"]

        sorted_indices = sorted(
            range(len(self.scores)), key=lambda s: self.scores[s], reverse=True
        )

        for i in sorted_indices:
            if self.scores[i] > 0 or self.moving_avg_scores[i] > 0:
                hotkey = self.metagraph.hotkeys[i]
                rows.append(
                    [
                        i,
                        f"{hotkey}",
                        f"{self.scores[i]:.8f}",
                        f"{self.moving_avg_scores[i]:.8f}",
                    ]
                )

        if not rows:
            logging.info(
                f"No active miners for {coin} (timeframe: {timeframe}) at Block {self.current_block}"
            )
            return

        from tabulate import tabulate

        table = tabulate(
            rows, headers=headers, tablefmt="grid", numalign="right", stralign="left"
        )

        title = f"Current Mining Scores - Block {self.current_block} - {coin.upper()} (Timeframe: {timeframe})"
        logging.info(f"Scores updated at block {self.current_block}")
        logging.info(f".\n{title}\n{table}")

    def save_state(self) -> None:
        """Save the current validator state to storage, including timestamp."""
        state = {
            "scores": self.scores,
            "moving_avg_scores": self.moving_avg_scores,
            "hotkeys": self.hotkeys,
            "block_at_registration": self.block_at_registration,
            "current_block": self.current_block,
            "last_evaluation_timestamp": self.last_evaluation_timestamp,
        }
        self.storage.save_state(state)
        logging.info(
            f"Saved validator state at block {self.current_block} with timestamp {self.last_evaluation_timestamp}"
        )

    def restore_state_and_evaluate(self) -> None:
        """
        Proxy specific: Attempt to restore validator state from storage.
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
        self.block_at_registration = state.get("block_at_registration", [])
        self.last_evaluation_timestamp = state.get("last_evaluation_timestamp", None)

        self.resync_metagraph()

        for idx in range(len(self.hotkeys)):
            # If the coldkey is a bad one, set the moving avg score to 0
            if self.metagraph.coldkeys[idx] in BAD_COLDKEYS:
                self.moving_avg_scores[idx] = 0.0

        logging.warning(f"Validator was down for {blocks_down} blocks.")
        self.evaluate_miner_share_value()

        logging.success(
            f"Successfully restored validator state with last evaluation timestamp: {self.last_evaluation_timestamp}"
        )

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

        success, err_msg = self.subtensor.set_weights(
            netuid=self.config.netuid,
            wallet=self.wallet,
            uids=list(range(len(self.hotkeys))),
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
                - Evaluate miner share value (polling every ~10 minutes).
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

                    self.evaluate_miner_share_value()

                    blocks_since_last_weights = self.subtensor.blocks_since_last_update(
                        self.config.netuid, self.uid
                    )
                    if blocks_since_last_weights >= self.weights_interval:
                        success, err_msg = self.set_weights()
                        if not success:
                            logging.error(f"Failed to set weights: {err_msg}")
                            continue

                    self.save_state()
                    validator_trust = self.subtensor.query_subtensor(
                        "ValidatorTrust",
                        params=[self.config.netuid],
                    )
                    normalized_validator_trust = (
                        validator_trust[self.uid] / U16_MAX
                        if validator_trust[self.uid] > 0
                        else 0
                    )

                    next_sync_block, sync_reason = self.get_next_sync_block()
                    logging.info(
                        f"Block: {self.current_block} | "
                        f"Next sync: {next_sync_block} | "
                        f"Sync reason: {sync_reason} | "
                        f"VTrust: {normalized_validator_trust:.2f}"
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


if __name__ == "__main__":
    load_dotenv()
    validator = TaohashProxyValidator()
    validator.run()
