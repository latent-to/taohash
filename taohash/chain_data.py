from taohash.node import Node
from bittensor_wallet import Wallet

def publish_pool_info(node: Node, wallet: Wallet, pool_info_bytes: bytes) -> None:
    # TODO: publish using commitments
    pass

def get_pool_info(node: Node, netuid: int, hotkey: str) -> bytes:
    # TODO: get using commitments
    pass