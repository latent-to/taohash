from typing import Dict

import cachetools.func
import requests
from ratelimit import limits, RateLimitException
from backoff import on_exception, expo

from ..api import PoolAPI

HASHRATE_TTL = 10 * 60  # 10min TTL for grabbing hashrate from all workers


class BraiinsPoolAPI(PoolAPI):
    __UNIT_TO_GHS: Dict[str, float] = {
        "H/s": 1e-9,
        "Kh/s": 1e-6,
        "Mh/s": 1e-3,
        "Gh/s": 1.0,
        "Th/s": 1e3,
        "Ph/s": 1e6,
    }

    __COIN_TO_COIN_NAME = {
        "bitcoin": "btc",
    }

    """
    An API for the Braiins pool monitoring
    See: https://academy.braiins.com/en/braiins-pool/monitoring/#overview
    """

    @classmethod
    def _hashrate_to_gh(cls, hashrate: float, unit: str) -> float:
        return cls.__UNIT_TO_GHS[unit] * hashrate

    @staticmethod
    def _worker_name_to_worker_id(worker_name: str) -> str:
        return worker_name.split(".", maxsplit=1)[1]

    @cachetools.func.ttl_cache(maxsize=64, ttl=HASHRATE_TTL)
    @on_exception(expo, RateLimitException, max_tries=8)
    @limits(calls=1, period=5)  # rate limit once per 5s
    def _get_shares_for_workers(self, coin: str) -> Dict[str, float]:
        coin_name = self.__COIN_TO_COIN_NAME[coin]
        url = f"https://pool.braiins.com/accounts/workers/json/{coin_name}"

        response = requests.get(
            url=url,
            headers={
                "X-SlushPool-Auth-Token": self.api_key,
                "accept": "application/json",
            },
        )

        result = response.json()
        workers = result[coin_name]["workers"]

        output = {
            self._worker_name_to_worker_id(worker_name): worker_data["shares_5m"]
            for worker_name, worker_data in workers.items()
        }

        return output

    def get_shares_for_worker(self, worker_id: str, coin: str) -> float:
        if coin != "bitcoin":
            raise ValueError("BraiinsPool only supports bitcoin")

        shares_for_all_workers = self._get_shares_for_workers(coin)

        return shares_for_all_workers.get(worker_id, 0.0)

    def get_fpps(self, coin: str) -> float:
        if coin != "bitcoin":
            raise ValueError("BraiinsPool only supports bitcoin")

        coin_name = self.__COIN_TO_COIN_NAME[coin]
        url = f"https://pool.braiins.com/stats/json/{coin_name}"

        response = requests.get(
            url=url,
            headers={
                "X-SlushPool-Auth-Token": self.api_key,
                "accept": "application/json",
            },
        )

        result = response.json()
        stats_data = result[coin_name]
        fpps = stats_data["fpps_rate"]

        return fpps
