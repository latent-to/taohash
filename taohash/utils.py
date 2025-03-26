from typing import Optional, Any, TypedDict

import netaddr
import bittensor

from .pool import PoolIndex, POOL_URLS_FMT


def ip_to_int(ip: str) -> int:
    return int(netaddr.IPAddress(ip))


def ip_version(ip: str) -> int:
    return netaddr.IPAddress(ip).version


def get_pool_from_axon(axon: bittensor.AxonInfo) -> Optional[str]:
    if not PoolIndex.has_value(axon.protocol):
        return None

    pool = PoolIndex[axon.protocol]
    pool_url = POOL_URLS_FMT[pool](axon)

    return pool_url


class Certificate(TypedDict):
    public_key: str  # hex str
    algorithm: int  # u8


def get_neuron_certificate(
    subtensor: bittensor.Subtensor, hotkey: str
) -> Optional[Certificate]:
    return subtensor.query_subtensor(
        "NeuronCertificates", params=[12, hotkey]
    ).serialize()


def get_pool_user_from_certificate(certificate: Certificate) -> Optional[str]:
    pass
