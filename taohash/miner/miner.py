#!/usr/bin/env python3
"""
Script to fetch and display subnet pool connection information for miners.

This script retrieves the subnet's mining pool details and formats them with the
appropriate worker name based on your wallet's hotkey.

Usage:
    python miner.py --wallet.name YOUR_WALLET --wallet.hotkey YOUR_HOTKEY --subtensor.network finney --btc_address YOUR_BTC_ADDRESS

    # Or for testnet
    python miner.py --wallet.name YOUR_WALLET --wallet.hotkey YOUR_HOTKEY --subtensor.network test --netuid 331 --btc_address YOUR_BTC_ADDRESS
"""

import argparse
import os
import sys

from bittensor import logging, Subtensor, config
from bittensor_wallet.bittensor_wallet import Wallet

from taohash.core.chain_data.pool_info import get_pool_info
from taohash.core.pool import PoolIndex


def get_subnet_pool_info():
    """Setup miner and display pool connection information."""

    parser = argparse.ArgumentParser(
        description="Get subnet pool connection information for mining"
    )
    parser.add_argument(
        "--netuid",
        type=int,
        default=os.getenv("NETUID", 14),
        help="The chain subnet uid (default: 14)",
    )
    parser.add_argument(
        "--subtensor.network",
        type=str,
        default=os.getenv("SUBTENSOR_NETWORK", "finney"),
        help="Bittensor network (default: finney)",
    )
    parser.add_argument(
        "--subtensor.chain_endpoint",
        type=str,
        default=os.getenv("SUBTENSOR_CHAIN_ENDPOINT"),
        help="Subtensor chain endpoint",
    )
    parser.add_argument(
        "--btc_address",
        type=str,
        default=os.getenv("BTC_ADDRESS"),
        help="Bitcoin address for receiving mining rewards (REQUIRED)",
        required=not os.getenv("BTC_ADDRESS"),
    )

    Wallet.add_args(parser)
    Subtensor.add_args(parser)
    logging.add_args(parser)

    config_obj = config(parser)

    logging(config=config_obj, logging_dir=config_obj.full_path)

    logging.info("Initializing wallet and subtensor...")
    wallet = Wallet(config=config_obj)
    subtensor = Subtensor(config=config_obj)

    logging.info(f"Network: {subtensor.network}")
    logging.info(f"Netuid: {config_obj.netuid}")
    logging.info(f"Wallet: {wallet}")

    logging.info("Checking wallet registration...")
    metagraph = subtensor.get_metagraph_info(netuid=config_obj.netuid)

    if wallet.hotkey.ss58_address not in metagraph.hotkeys:
        logging.error(
            f"\n❌ Your wallet {wallet} is not registered on subnet {config_obj.netuid}.\n"
            f"   Please run 'btcli subnet register' and try again."
        )
        sys.exit(1)

    uid = metagraph.hotkeys.index(wallet.hotkey.ss58_address)
    logging.success(f"✓ Wallet registered on subnet with UID: {uid}")

    btc_address = config_obj.btc_address
    if not btc_address:
        logging.error(
            "❌ BTC address is mandatory. Please set BTC_ADDRESS in .env or use --btc_address"
        )
        sys.exit(1)

    if not btc_address.startswith(("1", "3", "bc1")):
        logging.error(f"❌ Invalid BTC address format: {btc_address}")
        sys.exit(1)

    try:
        logging.info("Fetching subnet information...")
        owner_hotkey = subtensor.query_subtensor(
            "SubnetOwnerHotkey",
            params=[config_obj.netuid],
        )

        if not owner_hotkey:
            logging.error("Could not retrieve subnet owner information")
            sys.exit(1)

    except Exception as e:
        logging.error(f"Error fetching subnet owner: {e}")
        sys.exit(1)

    try:
        logging.info("Fetching pool information...")
        pool_info = get_pool_info(subtensor, config_obj.netuid, owner_hotkey)

        if not pool_info:
            logging.error("No pool information found for subnet")
            sys.exit(1)

        if pool_info.pool_index != PoolIndex.Proxy:
            logging.warning(
                f"Pool type is not Proxy (found: {pool_info.pool_index}). "
                f"This may not be a standard mining pool."
            )

    except Exception as e:
        logging.error(f"Error fetching pool info: {e}")
        sys.exit(1)

    hotkey = wallet.hotkey.ss58_address
    worker_suffix = hotkey[:4] + hotkey[-4:]
    worker_name = f"{btc_address}.{worker_suffix}"

    # Display complete setup status
    print("\n" + "=" * 60)
    print("MINING SETUP STATUS")
    print("=" * 60)
    print(f"\n✓ Wallet registered on subnet {config_obj.netuid}")
    print("✓ Pool information retrieved")

    print("\n" + "=" * 60)
    print("SUBNET POOL CONFIGURATION")
    print("=" * 60)

    print("\nNormal Pool:")
    print(f"  Stratum host: btc.taohash.com (or {pool_info.domain or pool_info.ip})")
    print(f"  Stratum port: {pool_info.port}")
    print(f"  Stratum username: {worker_name}")
    print(f"  Stratum password: {pool_info.password or 'x'}")

    if pool_info.high_diff_port:
        print("\nHigh Difficulty Pool:")
        print(
            f"  Stratum host: btc.taohash.com (or {pool_info.domain or pool_info.ip})"
        )
        print(f"  Stratum port: {pool_info.high_diff_port}")
        print(f"  Stratum username: {worker_name}")
        print(f"  Stratum password: {pool_info.password or 'x'}")
    else:
        print("\nHigh Difficulty Pool: Not available")
    print("\n\nSetting Minimum Difficulty:")
    print("  Use the password field: Eg: x;md=10000;")
    print("  Following the format is important")

    print("\n" + "=" * 60)
    print("Configure your miners with the above settings.")
    print("=" * 60 + "\n")

    # Additional helpful information
    print("Additional Information:")
    print(f"  Your UID: {uid}")
    print(f"  Your Hotkey: {hotkey}")
    print(f"  Worker Suffix: {worker_suffix}")
    print(f"  BTC Address: {btc_address}")

    if hasattr(pool_info, "extra_data") and pool_info.extra_data:
        if "description" in pool_info.extra_data:
            print(f"  Description: {pool_info.extra_data['description']}")


if __name__ == "__main__":
    try:
        get_subnet_pool_info()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)
