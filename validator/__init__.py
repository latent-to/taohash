import argparse
import bittensor as bt
from bittensor_wallet import Wallet

from taohash.pool import Pool
from taohash.pricing import CoinPriceAPI

TESTNET_NETUID = 332


class BaseValidator:
    def __init__(self):
        pass

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
