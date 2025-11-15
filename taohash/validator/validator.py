#! /usr/bin/env python3

# Copyright © 2025 Latent Holdings
# Licensed under MIT

import argparse
import os
import traceback
import time

from tabulate import tabulate

from bittensor import logging, Subtensor
from bittensor_wallet.bittensor_wallet import Wallet
from dotenv import load_dotenv

from taohash.core.chain_data.pool_info import (
    publish_pool_info,
    get_pool_info,
    encode_pool_info,
)
from taohash.core.constants import (
    VERSION_KEY,
    U16_MAX,
    OWNER_TAKE,
    SPLIT_WITH_MINERS,
    PAYOUT_FACTOR,
)
from taohash.core.pool import Pool, PoolBase
from taohash.core.pool.metrics import ProxyMetrics, get_metrics_timerange, EvaluationMetrics
from taohash.core.pool.proxy import ProxyPool, ProxyPoolAPI
from taohash.core.pool.proxy.config import ProxyPoolAPIConfig, ProxyPoolConfig
from taohash.core.pricing import CoinPriceAPI
from taohash.core.pricing.network_stats import get_current_difficulty
from taohash.validator import BaseValidator

SUPPORTED_COINS = ["btc", "bch"]

BAD_COLDKEYS = ["5CS96ckqKnd2snQ4rQKAvUpMh2pikRmCHb4H7TDzEt2AM9ZB"]


class TaohashProxyValidator(BaseValidator):
    """
    Taohash Proxy BTC Validator.

    This validator uses the Taohash proxy to retrieve miner statistics
    instead of directly querying the Braiins pool API.
    """

    def __init__(self):
        super().__init__()

        self.is_subnet_owner = False
        self.pools: dict[str, PoolBase] = {}
        self.config.coins = SUPPORTED_COINS
        self.setup_bittensor_objects()
        self.setup_remote_pool_access()
        self.price_api = CoinPriceAPI("coingecko", None)

        self.alpha = 0.8
        self.weights_interval = self.tempo

        self.evaluation_metrics = {}  # Per-coin evaluation metrics: {'btc': EvaluationMetrics, 'bch': EvaluationMetrics}
        self.scores = []  # Initialize to empty list to prevent AttributeError

    def add_args(self, parser: argparse.ArgumentParser):
        """Add validator arguments to the parser."""
        super().add_args(parser)

        ProxyPoolConfig.add_args(parser)
        ProxyPoolAPIConfig.add_args(parser)

    def setup_bittensor_objects(self):
        """
        Extend base setup with pool configuration and publishing.
        """
        super().setup_bittensor_objects()

        self.burn_uid = self.get_burn_uid()
        self.burn_hotkey = self.get_burn_hotkey()
        self.is_subnet_owner = self.burn_hotkey == self.wallet.hotkey.ss58_address

    def setup_remote_pool_access(self) -> None:
        """Create ProxyPool instances for each configured coin using env-provided credentials."""
        for coin in SUPPORTED_COINS:
            proxy_url, api_token = self._get_proxy_credentials_for_coin(coin)
            if not proxy_url:
                raise ValueError(
                    f"{coin.upper()}_POOL_API_URL environment variable must be set for coin '{coin}'"
                )
            if not api_token:
                raise ValueError(
                    f"{coin.upper()}_POOL_API_TOKEN environment variable must be set for coin '{coin}'"
                )

            api = ProxyPoolAPI(proxy_url=proxy_url, api_token=api_token, coin=coin)
            self.pools[coin] = ProxyPool(pool_info=None, api=api)

            logging.success(
                f"Connected to proxy API for {coin.upper()} at {proxy_url.rstrip('/')}"
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
            1. Determine time range per coin (last 10 minutes for first run, or since last evaluation)
            2. Fetch miner contributions from proxy for that time range
            3. Update scores for each miner based on share values
        """
        hotkey_to_uid = {hotkey: uid for uid, hotkey in enumerate(self.hotkeys)}

        current_time = int(time.time())

        for coin in self.config.coins:
            pool = self.pools.get(coin)
            if pool is None:
                logging.warning(
                    f"No proxy pool configured for {coin}. Skipping evaluation."
                )
                continue

            # Get or create evaluation metrics for this coin
            if coin not in self.evaluation_metrics:
                self.evaluation_metrics[coin] = EvaluationMetrics(coin, len(self.hotkeys))

            evaluation_metrics = self.evaluation_metrics[coin]
            coin_last_eval = evaluation_metrics.last_evaluation_timestamp
            if coin_last_eval:
                start_time = coin_last_eval
                end_time = current_time

                max_range = 24 * 60 * 60
                if end_time - start_time > max_range:
                    start_time = end_time - max_range

                logging.info(
                    f"Evaluating {coin.upper()} miners for time range: {start_time} to {end_time} ({end_time - start_time} seconds)"
                )
            else:
                end_time = current_time
                start_time = end_time - (10 * 60)
                logging.info(
                    f"First evaluation for {coin.upper()} - using last 10 minutes: {start_time} to {end_time}"
                )

            try:
                timerange_result = get_metrics_timerange(
                    pool,
                    self.hotkeys,
                    self.block_at_registration,
                    start_time,
                    end_time,
                    coin,
                )

                miner_metrics: list[ProxyMetrics] = timerange_result["metrics"]
                payout_factor = timerange_result["payout_factor"]

                # Update payout factor for this coin
                evaluation_metrics.payout_factor = (
                    payout_factor if payout_factor <= 1 else evaluation_metrics.payout_factor
                )

                coin_price = self.price_api.get_price(coin)
                coin_difficulty = get_current_difficulty(coin)

                share_rows = []
                for metric in miner_metrics:
                    if metric.hotkey not in hotkey_to_uid:
                        continue

                    uid = hotkey_to_uid[metric.hotkey]
                    share_value = metric.get_share_value_fiat(
                        coin_price, coin_difficulty, coin
                    )

                    # Accumulate raw score for this coin (without payout factor)
                    evaluation_metrics.add_score(uid, share_value)
                    if share_value > 0:
                        share_rows.append(
                            [
                                uid,
                                metric.hotkey,
                                f"{share_value:.8f}",
                            ]
                        )

                self._log_coin_share_table(
                    coin, share_rows, timeframe_seconds=end_time - start_time
                )

                # Update timestamp only for successful evaluation
                evaluation_metrics.last_evaluation_timestamp = current_time
                logging.info(f"Updated {coin.upper()} evaluation timestamp to {current_time}")

            except Exception as e:
                logging.error(
                    f"Failed to retrieve {coin.upper()} miner metrics for time range {start_time} to {end_time}: {e}. "
                    f"Keeping {coin.upper()} timestamp at {coin_last_eval}"
                )

    def _log_share_value_scores(self) -> None:
        """Log current scores based on share values from evaluated coins."""
        rows = []
        headers = ["UID", "Hotkey", "Score"]

        sorted_indices = sorted(
            range(len(self.scores)), key=lambda s: self.scores[s], reverse=True
        )

        for i in sorted_indices:
            if self.scores[i] > 0:
                hotkey = self.metagraph.hotkeys[i]
                rows.append(
                    [
                        i,
                        f"{hotkey}",
                        f"{self.scores[i]:.8f}",
                    ]
                )

        if not rows:
            logging.info(
                f"No active miners for {self.config.coins} at Block {self.current_block}"
            )
            return

        table = tabulate(
            rows, headers=headers, tablefmt="grid", numalign="right", stralign="left"
        )

        title = f"Current Mining Scores - Block {self.current_block} - Coins: {self.config.coins}"
        logging.info(f"Scores updated at block {self.current_block}")
        logging.info(f".\n{title}\n{table}")

    def _log_coin_share_table(
        self, coin: str, share_rows: list[list[str]], timeframe_seconds: int
    ) -> None:
        """Print per-coin share value contributions for the current evaluation cycle."""
        if not share_rows:
            logging.info(
                f"No valid share values for {coin.upper()} during timeframe {timeframe_seconds}s "
                f"at block {self.current_block}"
            )
            return

        share_table = tabulate(
            share_rows,
            headers=["UID", "Hotkey", f"{coin.upper()} Share Value"],
            tablefmt="outline",
            numalign="right",
            stralign="left",
        )
        title = f"Share value summary - {coin.upper()} (Timeframe: {timeframe_seconds}s) - Block {self.current_block}"
        logging.info(f".\n{title}\n{share_table}")

    def save_state(self) -> None:
        """Save the current validator state to storage."""
        # Convert evaluation metrics to dict for saving
        evaluation_metrics_data = {
            coin: metrics.to_dict()
            for coin, metrics in self.evaluation_metrics.items()
        }

        state = {
            "evaluation_metrics": evaluation_metrics_data,
            "hotkeys": self.hotkeys,
            "block_at_registration": self.block_at_registration,
            "current_block": self.current_block,
        }
        self.storage.save_state(state)
        logging.info(f"Saved validator state at block {self.current_block}")

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
        self.hotkeys = state.get("hotkeys", [])
        self.block_at_registration = state.get("block_at_registration", [])

        # Restore evaluation metrics
        self.evaluation_metrics = {}
        if "evaluation_metrics" in state:
            for coin, data in state["evaluation_metrics"].items():
                self.evaluation_metrics[coin] = EvaluationMetrics.from_dict(
                    coin, data, total_hotkeys
                )

        self.resync_metagraph()

        for idx in range(len(self.hotkeys)):
            # If the coldkey is a bad one, reset scores to 0 for all coins
            if self.metagraph.coldkeys[idx] in BAD_COLDKEYS:
                for metrics in self.evaluation_metrics.values():
                    metrics.scores[idx] = 0.0

        logging.warning(f"Validator was down for {blocks_down} blocks.")
        self.evaluate_miner_share_value()

        logging.success("Successfully restored validator state")

    def calculate_weights_distribution(self, total_value: float) -> list[float]:
        weights = [0.0] * len(self.hotkeys)
        tao_price = self.price_api.get_price("bittensor")
        subnet_price = self.subtensor.subnet(self.config.netuid).price.tao
        alpha_price = subnet_price * tao_price

        blocks_to_set_for = self.current_block - self.last_update
        alpha_to_dist = blocks_to_set_for * (1 - OWNER_TAKE) * SPLIT_WITH_MINERS
        value_to_dist = alpha_to_dist * alpha_price
        # Note: payout factors are already applied when merging coin scores
        scaled_total_value = total_value

        # Log per-coin payout factors from evaluation metrics
        if self.evaluation_metrics:
            payout_factors = {
                coin: metrics.payout_factor
                for coin, metrics in self.evaluation_metrics.items()
            }
            logging.info(f"Payout factors: {payout_factors}")

        if scaled_total_value > value_to_dist:
            weights = [score / scaled_total_value for score in self.scores]
        else:
            weights_to_dist = scaled_total_value / value_to_dist
            weights = [(score / total_value) * weights_to_dist for score in self.scores]

        sum_weights = sum(weights)
        remaining = max(0.0, 1.0 - sum_weights)
        if remaining > 0:
            weights[self.burn_uid] += remaining
        elif sum_weights > 1.0:
            weights = [w / sum_weights for w in weights]
        return weights

    def set_weights(self) -> tuple[bool, str]:
        """Set weights for all miners.

        Returns:
            tuple[bool, str]: A tuple containing:
                - bool: True if weights were set successfully, False otherwise
                - str: Error message if weights were not set successfully, empty string otherwise

        Evaluation:
            1. Merge coin scores with payout factors.
            2. Set weights using merged scores.
            3. Ensure miners are still active - otherwise burn the alpha.
            4. Reset scores for next evaluation.
        """
        # Merge evaluation metrics scores with their payout factors
        self.scores = [0.0] * len(self.hotkeys)
        for metrics in self.evaluation_metrics.values():
            weighted_scores = metrics.get_weighted_scores()
            for uid in range(len(self.hotkeys)):
                self.scores[uid] += weighted_scores[uid]

        # Log the merged scores before calculating weights
        self._log_share_value_scores()

        # Calculate weights
        total_value = sum(self.scores)
        if total_value == 0:
            logging.info("No miners are mining, we should burn the alpha")
            weights = [0.0] * len(self.hotkeys)
            weights[self.burn_uid] = 1.0
        else:
            weights = self.calculate_weights_distribution(total_value)

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
            # Reset evaluation metrics for next evaluation
            for metrics in self.evaluation_metrics.values():
                metrics.reset_scores(len(self.hotkeys))
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
