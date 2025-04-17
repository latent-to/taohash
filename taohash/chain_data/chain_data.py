from dataclasses import dataclass, field
import os
from typing import Optional, Any
import logging

import bt_decode
import netaddr
from bittensor import subtensor as bt_subtensor
from bittensor_wallet.bittensor_wallet import Wallet

from taohash.utils import ip_to_int


@dataclass
class PoolInfo:
    pool_index: int
    port: int
    ip: str | None = None
    domain: str | None = None
    username: str | None = None
    password: str | None = None
    extra_data: dict[str, Any] = field(default_factory=dict)

    def encode(self) -> bytes:
        return encode_pool_info(self)

    def to_raw(self) -> dict:
        return {
            "pool_index": self.pool_index,
            "ip": ip_to_int(self.ip) if self.ip else None,
            "port": self.port,
            "domain": self.domain,
            "username": self.username,
            "password": self.password,
        }

    def to_json(self) -> dict:
        return {
            "pool_index": self.pool_index,
            "ip": self.ip,
            "port": self.port,
            "domain": self.domain,
            "username": self.username,
            "password": self.password,
            "pool_url": self.pool_url,
            "extra_data": self.extra_data
        }

    @classmethod
    def decode(cls, pool_info_bytes: bytes) -> "PoolInfo":
        return decode_pool_info(pool_info_bytes)

    @property
    def pool_url(self) -> str:
        """Constructs the pool URL from domain/ip and port."""
        if self.domain:
            return f"{self.domain}:{self.port}"
        elif self.ip:
            return f"{self.ip}:{self.port}"
        else:
            # TODO: Handle this case - maybe raise an error
            return f":{self.port}"


def publish_pool_info(
    subtensor: bt_subtensor, netuid: int, wallet: "Wallet", pool_info_bytes: bytes
) -> bool:
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
    subtensor: bt_subtensor, netuid: int
) -> Optional[dict[str, PoolInfo]]:
    commitments = subtensor.get_all_commitments(netuid)
    if not commitments:
        return None

    all_pool_info: dict[str, PoolInfo] = {}
    for hotkey, raw_data in commitments.items():
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
    commitments = subtensor.get_all_commitments(netuid)
    if not commitments or hotkey not in commitments:
        return None

    try:
        raw_data = commitments[hotkey]

        if isinstance(raw_data, str):
            raw_bytes = bytes(raw_data, "latin1")
        elif isinstance(raw_data, bytes):
            raw_bytes = raw_data
        else:
            logging.error(f"Unexpected data type in commitments: {type(raw_data)}")
            return None

        return decode_pool_info(raw_bytes)
    except Exception as e:
        logging.error(f"Failed to get pool info: {e}")
        return None


def decode_pool_info(pool_info_bytes: bytes) -> PoolInfo:
    types_path = os.path.join(os.path.dirname(__file__), "types.json")
    with open(types_path, "r") as f:
        types = f.read()

    reg = bt_decode.PortableRegistry.from_json(types)

    data = bt_decode.decode("PoolInfo", reg, pool_info_bytes)

    if data["ip"] is not None:
        data["ip"] = str(netaddr.IPAddress(data["ip"]))

    return PoolInfo(**data)


def encode_pool_info(pool_info: PoolInfo) -> bytes:
    types_path = os.path.join(os.path.dirname(__file__), "types.json")
    with open(types_path, "r") as f:
        types = f.read()

    reg = bt_decode.PortableRegistry.from_json(types)

    raw_data = pool_info.to_raw()

    return bt_decode.encode("PoolInfo", reg, raw_data)
