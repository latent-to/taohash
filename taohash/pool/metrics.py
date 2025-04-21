from typing import List, Optional, Union

from dataclasses import dataclass
from bittensor import NeuronInfo, NeuronInfoLite
from substrateinterface import SubstrateInterface

from . import PoolBase


NETUID = 111  # TODO


@dataclass
class MiningMetrics:
    hotkey: str
    hash_rate_5m: float = 0.0  # In 5 minutes, hash rate in Gh/s
    hash_rate_60m: float = 0.0
    hash_rate_unit: str = "Gh/s"
    shares_5m: float = 0.0
    shares_60m: float = 0.0

    def get_value_last_5m(self, hash_price: float) -> float:
        hash_rate_th = (
            self.hash_rate_5m / 1000
            if self.hash_rate_unit == "Gh/s"
            else self.hash_rate_5m
        )
        # Value per day: hash_rate_th * hash_price (USD/TH/day)
        est_value_per_day = hash_rate_th * hash_price
        est_value_per_5m = est_value_per_day * (5 / 1440)  # 1440 mins per day
        return est_value_per_5m

    def get_value_last_day(self, hash_price: float) -> float:
        hash_rate_th = (
            self.hash_rate_60m / 1000
            if self.hash_rate_unit == "Gh/s"
            else self.hash_rate_60m
        )
        est_value_per_day = hash_rate_th * hash_price
        return est_value_per_day


def get_metrics_for_miner_by_hotkey(
    pool: PoolBase, hotkey_ss58: str, coin: str
) -> MiningMetrics:
    shares = pool.get_hotkey_contribution(hotkey_ss58, coin)
    return MiningMetrics(hotkey_ss58, shares["hash_rate_5m"])


def _get_hotkey_by_uid(node: SubstrateInterface, uid: int, netuid: int) -> int:
    pass


def get_metrics_for_miners(
    pool: PoolBase, neurons: List[Union[NeuronInfo, NeuronInfoLite]], coin: str
) -> List[MiningMetrics]:
    metrics = []
    all_workers = pool.get_all_miner_contributions(coin)

    for neuron in neurons:
        hotkey = neuron.hotkey
        worker_id = get_worker_id_for_hotkey(hotkey)
        worker_metrics = all_workers.get(worker_id, None)
        if worker_metrics is None:
            metrics.append(MiningMetrics(hotkey))
        else:
            metrics.append(
                MiningMetrics(
                    hotkey,
                    worker_metrics["hash_rate_5m"],
                    worker_metrics["hash_rate_60m"],
                    worker_metrics["hash_rate_unit"],
                    worker_metrics["shares_5m"],
                    worker_metrics["shares_60m"],
                )
            )
    return metrics

# TODO: Move to utils
def get_worker_id_for_hotkey(hotkey: str) -> str:
    return hotkey[:4] + hotkey[-4:]
