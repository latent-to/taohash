import hashlib
import time

import requests
from requests.exceptions import RequestException, JSONDecodeError
from ratelimit import limits, RateLimitException
from backoff import on_exception, expo

from bittensor import wallet
from taohash.core.pool.api import PoolAPI


class PrimaryPoolAPI(PoolAPI):
    """
    This client is used to communicate with the subnet's primary pool service.
    Authenticates all requests by signing them with the validator's hotkey.
    """

    def __init__(self, api_base: str, bt_wallet: wallet, timeout: float = 10.0):
        super().__init__(api_key="")
        self.api_base = api_base.rstrip("/")
        self.wallet = bt_wallet
        self.timeout = timeout

    def _auth_headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        timestamp = str(int(time.time()))
        canon = f"{method}\n{path}\n{timestamp}\n{body}"
        msg = (
            hashlib.blake2b(canon.encode(), digest_size=32).digest()
            if len(canon) > 256
            else canon.encode()
        )
        signature = self.wallet.hotkey.sign(msg).hex()
        return {
            "X-PubKey": self.wallet.hotkey.ss58_address,
            "X-Timestamp": timestamp,
            "X-Signature": signature,
            "Accept": "application/json",
        }

    @on_exception(
        expo, (RateLimitException, RequestException, JSONDecodeError), max_tries=5
    )
    @limits(calls=1, period=5)  # no more than 1 call every 5s
    def _request(self, method: str, path: str, body: str = "") -> requests.Response:
        """Unified, rate-limited + retry-backoff HTTP request."""
        url = f"{self.api_base}{path}"
        resp = requests.request(
            method,
            url,
            headers=self._auth_headers(method, path, body),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp

    @staticmethod
    def _worker_name_to_worker_id(worker_name: str) -> str:
        return worker_name.split(".", maxsplit=1)[1]

    def get_all_worker_data(self, pool_name: str) -> dict[str, dict]:
        path = f"/api/v1/miners/{pool_name}"
        response = self._request("GET", path)
        miners = response.json()["miners"]
        return {
            self._worker_name_to_worker_id(miner["miner_hotkey"]): miner
            for miner in miners
        }

    def get_worker_data(self, worker_id: str, pool_name: str) -> dict:
        path = f"/api/v1/miners/{pool_name}/{worker_id}"
        response = self._request("GET", path)
        return response.json()

    def get_fpps(self, coin: str) -> float:
        path = f"/api/v1/fpps/{coin}"
        response = self._request("GET", path)
        return float(response.json().get("rate", 0.0))
