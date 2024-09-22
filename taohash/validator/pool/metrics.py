from typing import List, Optional, Union

from dataclasses import dataclass
from bittensor import NeuronInfo, NeuronInfoLite
from substrateinterface import SubstrateInterface

from . import Pool


NETUID = 111  # TODO


@dataclass
class MiningMetrics:
    hotkey: str
    hashrate: float

    def get_hash_value(self, hashprice: float) -> float:
        return hashprice * self.hashrate


def get_metrics_for_miner_by_hotkey(pool: Pool, hotkey_ss58: str, coin: str = 'bitcoin') -> MiningMetrics:
    hashrate = pool.get_hashrate_for_hotkey(hotkey_ss58, coin)

    return MiningMetrics(hotkey_ss58, hashrate)


def _get_hotkey_by_uid(node: SubstrateInterface, uid: int, netuid: int) -> int:
    pass


def get_metrics_for_miners(
    pool: Pool, neurons: List[Union[NeuronInfo, NeuronInfoLite]], coin: str = 'bitcoin'
) -> List[MiningMetrics]:
    metrics = []
    for neuron in neurons:
        hotkey = neuron.hotkey
        neuron_metrics = get_metrics_for_miner_by_hotkey(pool, hotkey, coin)

        metrics.append(neuron_metrics)

    return metrics
