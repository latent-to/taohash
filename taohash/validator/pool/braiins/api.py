from typing import Dict

import cachetools.func
import requests
from ratelimit import limits, RateLimitException
from backoff import on_exception, expo

from ..api import PoolAPI

HASHRATE_TTL = 10 * 60  # 10min TTL for grabbing hashrate from all workers

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
    "litecoin": "ltc"
}


class BraiinsPoolAPI(PoolAPI):
    """
    An API for the Braiins pool monitoring
    See: https://academy.braiins.com/en/braiins-pool/monitoring/#overview
    """

    def _hashrate_to_gh(hashrate: float, unit: str) -> float:
        return __UNIT_TO_GHS[unit] * hashrate

    def _worker_name_to_worker_id(worker_name: str) -> str:
        return worker_name.split(".", maxsplit=1)[1]

    @cachetools.func.ttl_cache(maxsize=64, ttl=HASHRATE_TTL)
    @on_exception(expo, RateLimitException, max_tries=8)
    @limits(calls=1, period=5) # rate limit once per 5s
    def get_hashrate_for_workers(self, coin: str) -> Dict[str, float]:
        url = "https://pool.braiins.com/accounts/workers/json/btc"

        response = requests.get(
            url=url,
            headers={
                "X-SlushPool-Auth-Token": self.api_key,
                "accept": "application/json",
            },
        )

        result = response.json()
        coin_name = __COIN_TO_COIN_NAME[coin]
        workers = result[coin_name]["workers"]

        output = {
            self._worker_name_to_worker_id(worker_name): self._hashrate_to_gh(
                worker_data["hash_rate_scoring"]
            )
            for worker_name, worker_data in workers
        }

        return output

    def get_hashrate_for_worker(self, worker_id: str, coin: str) -> float:
        hashrate_for_all_workers = self.get_hashrate_for_workers(coin)

        return hashrate_for_all_workers.get(worker_id, 0.0)
