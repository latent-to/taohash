from typing import List, Optional, Union

from dataclasses import dataclass
from bittensor import NeuronInfo, NeuronInfoLite
from substrateinterface import SubstrateInterface

from . import PoolBase


NETUID = 111  # TODO


@dataclass
class MiningMetrics:
    hotkey: str
    shares: float
    hash_rate_gh: float

    def __init__(self, hotkey: str, shares: float, hash_rate_gh: float):
        self.hotkey = hotkey
        self.shares = shares
        self.hash_rate_gh = hash_rate_gh

    def get_value_last_hour(self, fpps: float) -> float:
        fpps_per_hour = fpps / 12
        # Convert hash rate from GH/s to TH/s
        hash_rate_th = self.hash_rate_gh / 1000
        # Fpps aggregated BTC/TH/Day
        return hash_rate_th * fpps_per_hour


def get_metrics_for_miner_by_hotkey(
    pool: PoolBase, hotkey_ss58: str, coin: str
) -> MiningMetrics:
    shares = pool.get_shares_for_hotkey(hotkey_ss58, coin)
    return MiningMetrics(hotkey_ss58, shares['shares_60m'], shares['avg_hashrate_60m_ghs'])


def _get_hotkey_by_uid(node: SubstrateInterface, uid: int, netuid: int) -> int:
    pass


def get_metrics_for_miners(
    pool: PoolBase, neurons: List[Union[NeuronInfo, NeuronInfoLite]], coin: str
) -> List[MiningMetrics]:
    metrics = []
    for neuron in neurons:
        hotkey = neuron.hotkey
        neuron_metrics = get_metrics_for_miner_by_hotkey(pool, hotkey, coin)

        metrics.append(neuron_metrics)

    return metrics
