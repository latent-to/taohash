from typing import Optional, TypedDict

import netaddr
import bittensor


def ip_to_int(ip: str) -> int:
    return int(netaddr.IPAddress(ip))


def ip_version(ip: str) -> int:
    return netaddr.IPAddress(ip).version


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
