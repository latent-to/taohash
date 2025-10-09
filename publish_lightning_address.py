#!/usr/bin/env python3
"""
Standalone script to publish or retrieve lightning address on Bittensor chain.

Usage:
    # Publish a lightning address
    python publish_lightning_address.py --wallet <wallet_name> --network <network> --netuid <netuid> --publish <lightning_address>
    
    # Retrieve your own lightning address
    python publish_lightning_address.py --wallet <wallet_name> --network <network> --netuid <netuid> --get
"""

import argparse
import sys
from typing import Optional

from bittensor import logging
from bittensor import subtensor as bt_subtensor
from bittensor_wallet.bittensor_wallet import Wallet

# Add the taohash module to path
sys.path.insert(0, '.')

from taohash.core.chain_data.lightning_address import (
    LightningAddress,
    publish_lightning_address,
    get_lightning_address,
)


def main():
    parser = argparse.ArgumentParser(
        description="Publish or retrieve lightning address on Bittensor chain"
    )
    
    # Required arguments
    parser.add_argument(
        "--wallet",
        type=str,
        required=True,
        help="Name of the wallet to use",
    )
    parser.add_argument(
        "--network",
        type=str,
        required=True,
        help="Network to connect to (e.g., finney, test, local)",
    )
    parser.add_argument(
        "--netuid",
        type=int,
        required=True,
        help="Network UID of the subnet",
    )
    
    # Action arguments (mutually exclusive)
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--publish",
        type=str,
        help="Lightning address to publish (e.g., user@getalby.com)",
    )
    action_group.add_argument(
        "--get",
        action="store_true",
        help="Retrieve your own lightning address",
    )
    
    # Optional arguments
    parser.add_argument(
        "--hotkey",
        type=str,
        default="default",
        help="Hotkey name (default: 'default')",
    )
    
    args = parser.parse_args()
    
    # Initialize wallet
    wallet = Wallet(name=args.wallet, hotkey=args.hotkey)
    
    # Initialize subtensor
    if args.network == "local":
        subtensor = bt_subtensor(network="ws://127.0.0.1:9944")
    else:
        subtensor = bt_subtensor(network=args.network)
    
    # Get the hotkey address
    hotkey_address = wallet.hotkey.ss58_address
    
    if args.publish:
        # Publish lightning address
        lightning_addr = LightningAddress(address=args.publish)
        encoded_bytes = lightning_addr.encode()
        
        print(f"Publishing lightning address: {args.publish}")
        print(f"Encoded size: {len(encoded_bytes)} bytes")
        print(f"Wallet: {args.wallet}")
        print(f"Hotkey: {hotkey_address}")
        print(f"Network: {args.network}")
        print(f"Netuid: {args.netuid}")
        
        # Confirm before publishing
        response = input("\nProceed with publishing? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return
        
        success = publish_lightning_address(
            subtensor=subtensor,
            netuid=args.netuid,
            wallet=wallet,
            lightning_address_bytes=encoded_bytes,
        )
        
        if success:
            print("✅ Lightning address published successfully!")
        else:
            print("❌ Failed to publish lightning address")
            sys.exit(1)
    
    elif args.get:
        # Retrieve lightning address
        print(f"Retrieving lightning address for hotkey: {hotkey_address}")
        print(f"Network: {args.network}")
        print(f"Netuid: {args.netuid}")
        
        lightning_addr = get_lightning_address(
            subtensor=subtensor,
            netuid=args.netuid,
            hotkey=hotkey_address,
        )
        
        if lightning_addr:
            print(f"\n✅ Lightning address found: {lightning_addr.address}")
        else:
            print("\n❌ No lightning address found for this hotkey")


if __name__ == "__main__":
    main()

