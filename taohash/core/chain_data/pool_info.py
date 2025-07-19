import os
from dataclasses import dataclass, field
from typing import Any, Optional

import bt_decode
from bittensor import logging
from bittensor import subtensor as bt_subtensor
from bittensor_wallet.bittensor_wallet import Wallet
from taohash.core.utils import ip_to_int


@dataclass
class PoolInfo:
    """
    Stratum pool information published by validators through blockchain commitments.

    This data structure contains all necessary details for miners to connect to
    validators' mining pools and provide hashrate. Validators publish this info
    to the blockchain, and miners retrieve it to establish connections.

    The extra_data field allows for extension with additional metadata that
    doesn't need to be encoded in the blockchain commitment.
    """

    pool_index: int
    port: int
    ip: str | None = None
    domain: str | None = None
    username: str | None = None
    password: str | None = None
    high_diff_port: int | None = None
    extra_data: dict[str, Any] = field(default_factory=dict)

    def encode(self) -> bytes:
        """
        Encode pool information to bytes for bittensor storage.

        Returns:
            Encoded bytes representation suitable for chain commitment
        """
        return encode_pool_info(self)

    def to_raw(self) -> dict:
        """
        Convert to raw dictionary format for encoding.

        Returns:
            Dictionary with pool information
        """
        return {
            "pool_index": self.pool_index,
            "ip": ip_to_int(self.ip) if self.ip else None,
            "port": self.port,
            "domain": self.domain,
            "username": self.username,
            "password": self.password,
            "high_diff_port": self.high_diff_port,
        }

    def to_json(self) -> dict:
        """
        Convert to complete JSON format with derived fields.

        Includes all fields plus computed pool_url and extra_data,
        suitable for API responses and storage.

        Returns:
            Complete dictionary representation with all fields
        """
        return {
            "pool_index": self.pool_index,
            "ip": self.ip,
            "port": self.port,
            "domain": self.domain,
            "username": self.username,
            "password": self.password,
            "high_diff_port": self.high_diff_port,
            "pool_url": self.pool_url,
            "extra_data": self.extra_data,
        }

    @classmethod
    def decode(cls, pool_info_bytes: bytes) -> "PoolInfo":
        """
        Create a PoolInfo instance from encoded bytes.

        Args:
            pool_info_bytes: Encoded pool information from blockchain

        Returns:
            Decoded PoolInfo instance
        """
        return decode_pool_info(pool_info_bytes)

    @property
    def pool_url(self) -> str:
        """
        Construct the pool URL from domain/IP and port.

        Returns:
            Formatted pool connection URL
        """
        if self.domain:
            return f"{self.domain}:{self.port}"
        elif self.ip:
            return f"{self.ip}:{self.port}"
        else:
            # TODO: Handle this case - maybe raise an error
            return f":{self.port}"

    @property
    def high_diff_pool_url(self) -> str:
        """
        Construct the high difficulty pool URL.

        If high_diff_port is set, uses that port. Otherwise falls back to regular pool_url.

        Returns:
            Formatted high difficulty pool connection URL
        """
        if self.high_diff_port is None:
            return self.pool_url

        if self.domain:
            return f"{self.domain}:{self.high_diff_port}"
        elif self.ip:
            return f"{self.ip}:{self.high_diff_port}"
        else:
            return f":{self.high_diff_port}"


def publish_pool_info(
    subtensor: bt_subtensor, netuid: int, wallet: "Wallet", pool_info_bytes: bytes
) -> bool:
    """
    Publish mining pool information to the blockchain as a validator commitment.

    Validators call this function to publish their pool connection details,
    making them available to miners in the subnet. Each validator can have
    only one active commitment at a time.

    Args:
        subtensor: Subtensor instance
        netuid: Network UID of the subnet
        wallet: Validator's wallet with hotkey for signing
        pool_info_bytes: Encoded pool information (max 128 bytes)

    Returns:
        Boolean indicating success of the transaction

    Raises:
        ValueError: If pool_info_bytes exceeds 128 bytes
    """
    if len(pool_info_bytes) > 128:
        raise ValueError("Pool info bytes must be at most 128 bytes")

    pool_info_call = subtensor.substrate.compose_call(
        call_module="Commitments",
        call_function="set_commitment",
        call_params={
            "netuid": netuid,
            "info": {"fields": [[{f"Raw{len(pool_info_bytes)}": pool_info_bytes}]]},
        },
    )

    extrinsic = subtensor.substrate.create_signed_extrinsic(
        call=pool_info_call, keypair=wallet.hotkey
    )
    response = subtensor.substrate.submit_extrinsic(
        extrinsic=extrinsic,
        wait_for_inclusion=True,
        wait_for_finalization=True,
    )

    return response.is_success


def get_all_pool_info(
    subtensor: bt_subtensor, netuid: int, valid_hotkeys: list[str]
) -> Optional[dict[str, PoolInfo]]:
    """
    Retrieve all validators' pool information from the blockchain.

    Used by miners to discover all available mining pools in the subnet.
    Returns a dictionary mapping validator hotkeys to their pool information.

    Args:
        subtensor: Subtensor instance for blockchain interaction
        netuid: Network UID of the subnet

    Returns:
        Dictionary mapping validator hotkeys to their PoolInfo objects,
        or None if no commitments are found
    """
    commitments = subtensor.get_all_commitments(netuid)
    if not commitments:
        return None

    all_pool_info: dict[str, PoolInfo] = {}
    for hotkey, raw_data in commitments.items():
        if hotkey not in valid_hotkeys:
            continue

        try:
            if isinstance(raw_data, str):
                raw_bytes = bytes(raw_data, "latin1")
            elif isinstance(raw_data, bytes):
                raw_bytes = raw_data
            else:
                logging.error(f"Unexpected data type in commitments: {type(raw_data)}")
                continue

            pool_info = decode_pool_info(raw_bytes)
            all_pool_info[hotkey] = pool_info
        except Exception as e:
            logging.error(f"Failed to decode pool info: {e}")
            continue

    return all_pool_info


def get_pool_info(
    subtensor: bt_subtensor, netuid: int, hotkey: str
) -> Optional[PoolInfo]:
    """
    Retrieve pool information for a specific validator.

    Used when a miner needs to connect to a specific validator's pool.

    Args:
        subtensor: Subtensor instance
        netuid: Network UID of the subnet
        hotkey: Validator's hotkey SS58 address

    Returns:
        PoolInfo object if found, None otherwise
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
            
            return decode_pool_info(raw_bytes)
        except Exception as e:
            logging.debug(f"Failed to decode pool info (might be miner commitment): {e}")
            return None
            
    except Exception as e:
        logging.debug(f"Error retrieving pool info: {e}")
        return None


def decode_pool_info(pool_info_bytes: bytes) -> PoolInfo:
    """
    Decode binary pool information into a PoolInfo object.

    Uses the PoolInfo schema defined in types.json to decode
    the binary data from blockchain commitments.

    Args:
        pool_info_bytes: Encoded pool information from blockchain

    Returns:
        Decoded PoolInfo instance with human-readable values
    """

    types_path = os.path.join(os.path.dirname(__file__), "types.json")
    with open(types_path, "r") as f:
        types = f.read()

    reg = bt_decode.PortableRegistry.from_json(types)

    try:
        data = bt_decode.decode("PoolInfo", reg, pool_info_bytes)
    except ValueError as e:
        if "Failed to decode type" in str(e):
            # Old data - fallback mechanism
            scale_bytes_with_none = pool_info_bytes + b"\x00"
            try:
                data = bt_decode.decode("PoolInfo", reg, scale_bytes_with_none)
            except Exception:
                raise e
        else:
            raise

    return PoolInfo(**data)


def encode_pool_info(pool_info: PoolInfo) -> bytes:
    """
    Encode a PoolInfo object into binary format for bittensor storage.

    Converts the PoolInfo into a compact binary representation
    suitable for storage in chain commitments.

    Args:
        pool_info: PoolInfo instance to encode

    Returns:
        Binary encoded data ready for bittensor storage
    """
    types_path = os.path.join(os.path.dirname(__file__), "types.json")
    with open(types_path, "r") as f:
        types = f.read()

    reg = bt_decode.PortableRegistry.from_json(types)

    raw_data = pool_info.to_raw()

    return bt_decode.encode("PoolInfo", reg, raw_data)
