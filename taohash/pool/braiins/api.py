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

COIN_TO_COIN_NAME: Dict[str, str] = {
    "bitcoin": "btc",
}


class BraiinsPoolAPI(PoolAPI):
    """
    An API for the Braiins pool monitoring
    See: https://academy.braiins.com/en/braiins-pool/monitoring/#overview
    """

    def __init__(self, api_key: str, user_id: str, password: str):
        """
        Initialize BraiinsPoolAPI with required authentication credentials.

        Args:
            api_key (str): The API key for Braiins pool
            user_id (str): User ID for miners
            password (str): Password for miners
        """
        super().__init__(api_key)
        if not user_id or not password:
            raise ValueError("Both user_id and password are required for Braiins pool")
        self.user_id = user_id
        self.password = password

    def _hashrate_to_gh(hashrate: float, unit: str) -> float:
        """
        Convert hashrate from a given unit to Gigahashes per second.
        """
        return __UNIT_TO_GHS[unit] * hashrate

    def _worker_name_to_worker_id(worker_name: str) -> str:
        """
        Extract the worker ID from a worker name (assumes format 'prefix.workerID').
        """
        return worker_name.split(".", maxsplit=1)[1]

    @cachetools.func.ttl_cache(maxsize=64, ttl=HASHRATE_TTL)
    @on_exception(expo, RateLimitException, max_tries=8)
    @limits(calls=1, period=5)  # rate limit once per 5s
    def _get_shares_for_workers(self, coin: str) -> Dict[str, float]:
        if coin != "bitcoin":
            raise ValueError("BraiinsPool only supports bitcoin")

        coin_name = COIN_TO_COIN_NAME[coin]
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
            self._worker_name_to_worker_id(worker_name): self._hashrate_to_gh(
                worker_data["shares_5m"]
            )
            for worker_name, worker_data in workers
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

        coin_name = COIN_TO_COIN_NAME[coin]
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
