from dataclasses import dataclass

import bt_decode
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

    def encode(self) -> bytes:
        return encode_pool_info(self)

    def to_raw(self) -> dict:
        fields = ["pool_index", "ip", "domain", "port", "username", "password"]
        pool_info_raw = {field: getattr(self, field, default=None) for field in fields}

        pool_info_raw["pool_index"] = self.pool_index.value
        pool_info_raw["ip"] = ip_to_int(self.ip) if self.ip else None

        return pool_info_raw

    @classmethod
    def decode(cls, pool_info_bytes: bytes) -> "PoolInfo":
        return decode_pool_info(pool_info_bytes)


def publish_pool_info(
    subtensor: bt_subtensor, netuid: int, wallet: "Wallet", pool_info_bytes: bytes
) -> bool:
    wallet.hotkey
    if len(pool_info_bytes) > 128:
        raise ValueError("Pool info bytes must be at most 128 bytes")

    pool_info_bytes_length = len(pool_info_bytes)
    pool_info_call = subtensor.substrate.compose_call(
        "Commitments",
        "set_commitment",
        call_params={
            "netuid": netuid,
            "info": {"fields": [{f"Raw{pool_info_bytes_length}": pool_info_bytes}]},
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


def get_pool_info(subtensor: bt_subtensor, netuid: int, hotkey: str) -> bytes:
    commitments = subtensor.query_module(
        "Commitments",
        "commitment_of",
        params=[netuid, hotkey],
    )
    if commitments is None:
        return None
    return commitments["info"]["fields"][0]["Raw128"]


def decode_pool_info(pool_info_bytes: bytes) -> PoolInfo:
    with open("types.json", "r") as f:
        types = f.read()

    reg = bt_decode.PortableRegistry.from_json(types)

    return bt_decode.bt_decode("PoolInfo", reg, pool_info_bytes)


def encode_pool_info(pool_info: PoolInfo) -> bytes:
    with open("types.json", "r") as f:
        types = f.read()

    reg = bt_decode.PortableRegistry.from_json(types)

    return bt_decode.bt_encode("PoolInfo", reg, pool_info.to_raw())
