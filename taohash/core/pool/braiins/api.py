import bittensor as bt
import requests
from backoff import on_exception, expo
from ratelimit import limits, RateLimitException
from requests.exceptions import RequestException, JSONDecodeError

from taohash.core.pool.api import PoolAPI


class BraiinsPoolConnectionError(Exception):
    """Custom exception for Braiins Pool API errors"""

    pass


class BraiinsPoolAPI(PoolAPI):
    def __init__(self, api_key: str) -> None:
        super().__init__(api_key)
        if not self.test_connection():
            bt.logging.error(
                "Failed to connect to Braiins Pool API. Please check your API key and try again."
            )
            raise BraiinsPoolConnectionError(
                "Failed to connect to Braiins Pool API. Please check your API key and try again."
            )
        else:
            bt.logging.success("Successfully pinged Braiins Pool API.")

    __UNIT_TO_GHS: dict[str, float] = {
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
        splits = worker_name.split(".", maxsplit=1)
        if len(splits) == 1:  # no period
            return splits[0]
        else:
            return splits[1]

    @on_exception(
        expo, (RateLimitException, RequestException, JSONDecodeError), max_tries=8
    )
    @limits(calls=1, period=5)  # rate limit once per 5s
    def _get_worker_data(self, coin: str) -> dict[str, float]:
        coin_name = self.__COIN_TO_COIN_NAME[coin]
        url = f"https://pool.braiins.com/accounts/workers/json/{coin_name}"

        response = requests.get(
            url=url,
            headers={
                "X-SlushPool-Auth-Token": self.api_key,
                "accept": "application/json",
            },
        )
        response.raise_for_status()

        result = response.json()
        workers = result[coin_name]["workers"]
        output = {
            self._worker_name_to_worker_id(worker_name): {**worker_data}
            for worker_name, worker_data in workers.items()
        }

        return output

    def get_all_worker_data(self, coin: str) -> dict:
        if coin != "bitcoin":
            raise ValueError("BraiinsPool only supports bitcoin")

        return self._get_worker_data(coin)

    def get_worker_data(self, worker_id: str, coin: str) -> dict:
        if coin != "bitcoin":
            raise ValueError("BraiinsPool only supports bitcoin")

        workers_data = self._get_worker_data(coin)
        return workers_data.get(worker_id, None)

    @on_exception(
        expo, (RateLimitException, RequestException, JSONDecodeError), max_tries=8
    )
    @limits(calls=1, period=5)  # rate limit once per 5s
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
        response.raise_for_status()

        result = response.json()
        stats_data = result[coin_name]
        fpps = stats_data["fpps_rate"]

        return fpps

    def test_connection(self) -> bool:
        """Test API connection and credentials"""
        try:
            self.get_fpps("bitcoin")
            return True
        except Exception as e:
            bt.logging.error(f"Failed to connect to Braiins Pool API: {str(e)}")
            return False
