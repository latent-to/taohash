#!/usr/bin/env python3
"""
Script to fetch and display subnet pool connection information for miners.

This script retrieves the subnet's mining pool details and formats them with the
appropriate worker name based on your wallet's hotkey.

Usage:
    python taohash_mining_info.py --wallet.name YOUR_WALLET --wallet.hotkey YOUR_HOTKEY
    
    # Or with network specification
    python taohash_mining_info.py --wallet.name YOUR_WALLET --wallet.hotkey YOUR_HOTKEY --subtensor.network finney
    
    # Or for testnet
    python taohash_mining_info.py --wallet.name YOUR_WALLET --wallet.hotkey YOUR_HOTKEY --subtensor.network test --netuid 91
"""

import argparse
import os
import sys

from bittensor import logging, Subtensor, config
from bittensor_wallet.bittensor_wallet import Wallet

from taohash.core.chain_data.pool_info import get_pool_info
from taohash.core.pool import PoolIndex


def get_subnet_pool_info():
    """Fetch and display subnet pool connection information."""
    
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
    
    try:
        logging.info("Fetching subnet information...")
        owner_hotkey = subtensor.query_subtensor(
            "SubnetOwnerHotkey",
            params=[config_obj.netuid],
        )
        
        if not owner_hotkey:
            logging.error("Could not retrieve subnet owner information")
            sys.exit(1)
            
        logging.info(f"Subnet owner hotkey: {owner_hotkey}")
        
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
    worker_name = f"{pool_info.username}.{worker_suffix}"
    
    # Display information
    print("\n" + "="*50)
    print("SUBNET POOL CONFIGURATION")
    print("="*50)
    
    print("\nNormal Pool:")
    print(f"  URL: {pool_info.domain or pool_info.ip}:{pool_info.port}")
    print(f"  Worker: {worker_name}")
    print(f"  Password: {pool_info.password or 'x'}")
    
    if pool_info.high_diff_port:
        print("\nHigh Difficulty Pool:")
        print(f"  URL: {pool_info.domain or pool_info.ip}:{pool_info.high_diff_port}")
        print(f"  Worker: {worker_name}")
        print(f"  Password: {pool_info.password or 'x'}")
    else:
        print("\nHigh Difficulty Pool: Not available")
    print("\n\nSetting Minimum Difficulty:")
    print("  Use the password field: Eg: x;md=10000;")
    print("  Following the format is important")
    
    print("\n" + "="*50)
    print("Configure your miners with the above settings.")
    print("="*50 + "\n")
    
    # Additional helpful information
    print("Additional Information:")
    print(f"  Your Hotkey: {hotkey}")
    print(f"  Worker Suffix: {worker_suffix}")
    print(f"  Pool Type: {'Proxy' if pool_info.pool_index == PoolIndex.Proxy else 'Other'}")
    
    if hasattr(pool_info, 'extra_data') and pool_info.extra_data:
        if 'description' in pool_info.extra_data:
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