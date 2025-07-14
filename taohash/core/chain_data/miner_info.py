import os
from dataclasses import dataclass
from typing import Optional

import bt_decode
from bittensor import logging
from bittensor import Subtensor
from bittensor_wallet.bittensor_wallet import Wallet


@dataclass
class MinerInfo:
    """
    Miner information published by miners through Bittensor commitments.

    This data structure contains the BTC address where miners receive rewards.
    Miners publish this info to the blockchain to associate their hotkey with
    their BTC payout address.
    """

    btc_address: str

    def encode(self) -> bytes:
        """
        Encode miner information to bytes for bittensor storage.

        Returns:
            Encoded bytes representation suitable for chain commitment
        """
        return encode_miner_info(self)

    def to_raw(self) -> dict:
        """
        Convert to raw dictionary format for encoding.

        Returns:
            Dictionary with miner information
        """
        return {
            "btc_address": self.btc_address,
        }

    @classmethod
    def decode(cls, miner_info_bytes: bytes) -> "MinerInfo":
        """
        Create a MinerInfo instance from encoded bytes.

        Args:
            miner_info_bytes: Encoded miner information from blockchain

        Returns:
            Decoded MinerInfo instance
        """
        return decode_miner_info(miner_info_bytes)

    @classmethod
    def from_btc_address(cls, btc_address: str) -> "MinerInfo":
        """
        Create a MinerInfo instance from a BTC address.

        Args:
            btc_address: Bitcoin address string

        Returns:
            MinerInfo instance
        """
        return cls(btc_address=btc_address)


def publish_miner_info(
    subtensor: Subtensor, netuid: int, wallet: "Wallet", miner_info_bytes: bytes
) -> bool:
    """
    Publish miner BTC address information to the blockchain as a commitment.

    Miners call this function to publish their BTC payout address,
    making it available on-chain. Each miner can have only one active
    commitment at a time.

    Args:
        subtensor: Subtensor instance
        netuid: Network UID of the subnet
        wallet: Miner's wallet with hotkey for signing
        miner_info_bytes: Encoded miner information (max 128 bytes)

    Returns:
        Boolean indicating success of the transaction

    Raises:
        ValueError: If miner_info_bytes exceeds 128 bytes
    """
    if len(miner_info_bytes) > 128:
        raise ValueError("Miner info bytes must be at most 128 bytes")

    miner_info_call = subtensor.substrate.compose_call(
        call_module="Commitments",
        call_function="set_commitment",
        call_params={
            "netuid": netuid,
            "info": {"fields": [[{f"Raw{len(miner_info_bytes)}": miner_info_bytes}]]},
        },
    )

    extrinsic = subtensor.substrate.create_signed_extrinsic(
        call=miner_info_call, keypair=wallet.hotkey
    )
    response = subtensor.substrate.submit_extrinsic(
        extrinsic=extrinsic,
        wait_for_inclusion=True,
        wait_for_finalization=True,
    )

    return response.is_success


def get_miner_info(
    subtensor: Subtensor, netuid: int, hotkey: str
) -> Optional[MinerInfo]:
    """
    Retrieve miner information for a specific miner.

    Used to get the BTC address associated with a miner's hotkey.

    Args:
        subtensor: Subtensor instance
        netuid: Network UID of the subnet
        hotkey: Miner's hotkey SS58 address

    Returns:
        MinerInfo object if found and decodable, None otherwise
    """
    try:
        commit_data = subtensor.substrate.query(
            module="Commitments",
            storage_function="CommitmentOf",
            params=[netuid, hotkey],
        )

        if not commit_data:
            return None

        try:
            commitment = commit_data["info"]["fields"][0][0]
            bytes_key = next(iter(commitment.keys()))
            bytes_tuple = commitment[bytes_key][0]
            raw_bytes = bytes(bytes_tuple)

            return decode_miner_info(raw_bytes)
        except Exception as e:
            logging.debug(
                f"Failed to decode miner info (might be validator commitment): {e}"
            )
            return None

    except Exception as e:
        logging.debug(f"Error retrieving miner info: {e}")
        return None


def decode_miner_info(miner_info_bytes: bytes) -> MinerInfo:
    """
    Decode binary miner information into a MinerInfo object.

    Uses the MinerInfo schema defined in types.json to decode
    the binary data from blockchain commitments.

    Args:
        miner_info_bytes: Encoded miner information from blockchain

    Returns:
        Decoded MinerInfo instance
    """
    types_path = os.path.join(os.path.dirname(__file__), "types.json")
    with open(types_path, "r") as f:
        types = f.read()

    reg = bt_decode.PortableRegistry.from_json(types)

    try:
        data = bt_decode.decode("MinerInfo", reg, miner_info_bytes)
    except ValueError as e:
        raise e

    return MinerInfo(**data)


def encode_miner_info(miner_info: MinerInfo) -> bytes:
    """
    Encode a MinerInfo object into binary format for bittensor storage.

    Converts the MinerInfo into a compact binary representation
    suitable for storage in chain commitments.

    Args:
        miner_info: MinerInfo instance to encode

    Returns:
        Binary encoded data ready for bittensor storage
    """
    types_path = os.path.join(os.path.dirname(__file__), "types.json")
    with open(types_path, "r") as f:
        types = f.read()

    reg = bt_decode.PortableRegistry.from_json(types)

    raw_data = miner_info.to_raw()

    return bt_decode.encode("MinerInfo", reg, raw_data)
