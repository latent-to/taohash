import argparse
import copy
import bittensor as bt
from bittensor_wallet import Wallet

from tabulate import tabulate
from taohash.core.pool import Pool
from taohash.core.pricing import CoinPriceAPI

TESTNET_NETUID = 332


class BaseValidator:
    def __init__(self):
        """Base initialization for all validator instances.
        """
        self.config = None
        self.subtensor = None
        self.wallet = None
        self.metagraph = None

        self.last_update = 0
        self.current_block = 0
        self.scores = []
        self.moving_avg_scores = []
        self.alpha = None

    def add_args(self, run_command_parser: argparse.ArgumentParser):
        run_command_parser.add_argument(
            "--worker_prefix",
            required=False,
            default="",
            help="A prefix for the workers names miners will use.",
        )
        # Adds override arguments for network and netuid.
        run_command_parser.add_argument(
            "--netuid", type=int, default=TESTNET_NETUID, help="The chain subnet uid."
        )

        run_command_parser.add_argument(
            "--eval_interval",
            type=int,
            default=10,
            help="The interval on which to run evaluation across the metagraph.",
        )

        # run_command_parser.add_argument(
        #     "--coins",
        #     type=str,
        #     nargs="+",
        #     default=["bitcoin"],
        #     help="The coins you wish to reward miners for. Use CoinGecko token naming",
        # )

        # Adds subtensor specific arguments.
        bt.subtensor.add_args(run_command_parser)
        # Adds logging specific arguments.
        bt.logging.add_args(run_command_parser)
        # Adds wallet specific arguments.
        Wallet.add_args(run_command_parser)
        Pool.add_args(run_command_parser)
        CoinPriceAPI.add_args(run_command_parser)

    def setup_logging(self):
        # Set up logging.
        bt.logging(config=self.config, logging_dir=self.config.full_path)
        bt.logging.info(
            f"Running validator for subnet: {self.config.netuid} on network: {self.config.subtensor.network} with config:\n{self.config}"
        )

    def resync_metagraph(self):
        """
        Resyncs the metagraph and updates the score arrays to handle:
        1. New registrations (metagraph size increase)
        2. Hotkey replacements at existing UIDs
        """
        bt.logging.info("Resyncing metagraph...")

        # Backup current state
        previous_metagraph = copy.deepcopy(self.metagraph)
        previous_hotkeys = previous_metagraph.hotkeys

        # Sync metagraph
        self.metagraph.sync(subtensor=self.subtensor)
        self.current_block = self.metagraph.block.item()

        # Check for changes
        if previous_metagraph.axons == self.metagraph.axons:
            bt.logging.debug("No metagraph changes detected")
            return

        bt.logging.info("Metagraph updated, handling registrations and replacements")

        # 1. Handle hotkey replacements at existing UIDs
        for uid, hotkey in enumerate(previous_hotkeys):
            if (
                uid < len(self.metagraph.hotkeys)
                and hotkey != self.metagraph.hotkeys[uid]
            ):
                bt.logging.info(
                    f"Hotkey replaced at uid {uid}: {hotkey} -> {self.metagraph.hotkeys[uid]}"
                )
                # Reset scores for replaced hotkeys
                self.scores[uid] = 0.0
                self.moving_avg_scores[uid] = 0.0

        # 2. Handle new registrations
        if len(previous_hotkeys) < len(self.metagraph.hotkeys):
            old_size = len(previous_hotkeys)
            new_size = len(self.metagraph.hotkeys)
            bt.logging.info(f"Metagraph size increased from {old_size} to {new_size}")

            new_scores = [0.0] * new_size
            new_moving_avg = [0.0] * new_size

            # Copy existing scores to the new arrays
            for i in range(min(old_size, len(self.scores))):
                new_scores[i] = self.scores[i]
                new_moving_avg[i] = self.moving_avg_scores[i]

            self.scores = new_scores
            self.moving_avg_scores = new_moving_avg

            # Log new registrations
            for uid in range(old_size, new_size):
                bt.logging.info(
                    f"New registration at uid {uid}: {self.metagraph.hotkeys[uid]}"
                )

        bt.logging.info(f"Metagraph sync complete at block {self.current_block}")

    def _log_weights_and_scores(self, weights):
        """Log weights and moving average scores in a tabular format."""
        rows = []
        headers = ["UID", "Hotkey", "Moving Avg", "Weight", "Normalized (%)"]

        # Sort by weight (highest first)
        sorted_indices = sorted(
            range(len(weights)), key=lambda i: weights[i], reverse=True
        )

        for i in sorted_indices:
            if weights[i] > 0 or self.moving_avg_scores[i] > 0:
                hotkey = self.metagraph.hotkeys[i]
                rows.append(
                    [
                        i,
                        f"{hotkey}",
                        f"{self.moving_avg_scores[i]:.8f}",
                        f"{weights[i]:.8f}",
                        f"{weights[i] * 100:.2f}%",
                    ]
                )

        if not rows:
            bt.logging.info(
                f"No miners receiving weights at Block {self.current_block}"
            )
            return

        table = tabulate(
            rows, headers=headers, tablefmt="grid", numalign="right", stralign="left"
        )
        title = f"Weights set at Block: {self.current_block}"
        bt.logging.info(f"{title}\n{table}")

    def _log_scores(self, coin: str, hash_price: float):
        """Log current scores in a tabular format with hotkeys."""
        rows = []
        headers = ["UID", "Hotkey", "Score", "Moving Avg"]

        # Sort by score (highest first)
        sorted_indices = sorted(
            range(len(self.scores)), key=lambda i: self.scores[i], reverse=True
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
            bt.logging.info(
                f"No active miners for {coin} (hash price: ${hash_price:.8f}) at Block {self.current_block}"
            )
            return

        table = tabulate(
            rows, headers=headers, tablefmt="grid", numalign="right", stralign="left"
        )

        title = f"Current Mining Scores - Block {self.current_block} - {coin.upper()} (Hash Price: ${hash_price:.8f})"
        bt.logging.info(f"Scores updated at block {self.current_block}")
        bt.logging.info(f".\n{title}\n{table}")
