from bittensor import subtensor as bt_subtensor
from bittensor_wallet.bittensor_wallet import Wallet


def publish_pool_info(
    subtensor: bt_subtensor, wallet: "Wallet", pool_info_bytes: bytes
) -> None:
    # TODO: publish using commitments
    pass


def get_pool_info(subtensor: bt_subtensor, netuid: int, hotkey: str) -> bytes:
    # TODO: get using commitments
    pass
