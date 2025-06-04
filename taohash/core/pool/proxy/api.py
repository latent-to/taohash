import httpx
from typing import Optional, Any

from bittensor import logging

from taohash.core.pool.pool import PoolAPI


class ProxyPoolConnectionError(Exception):
    """Custom exception for Proxy Pool API errors"""

    pass


class ProxyPoolAPI(PoolAPI):
    """
    API client for interacting with the Taohash proxy.

    The proxy provides worker statistics via REST API with Bearer token authentication.
    """

    def __init__(self, proxy_url: str, api_token: str):
        self.proxy_url = proxy_url.rstrip("/")
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

        if not self.test_connection():
            logging.error(
                "Failed to connect to Proxy Pool API. Please check your proxy URL and API token."
            )
            raise ProxyPoolConnectionError(
                "Failed to connect to Proxy Pool API. Please check your proxy URL and API token."
            )
        else:
            logging.success("Successfully connected to Proxy Pool API.")

    @staticmethod
    def _worker_name_to_worker_id(worker_name: str) -> str:
        splits = worker_name.split(".", maxsplit=1)
        if len(splits) == 1:  # no period
            return splits[0]
        else:
            return splits[1]

    def get_worker_data(
        self, worker_id: str, coin: str = "bitcoin"
    ) -> Optional[dict[str, Any]]:
        """
        Get worker data from the proxy API.

        Args:
            worker_id: The worker ID (hotkey)
            coin: The coin type (default: "bitcoin")

        Returns:
            Worker data dict with hash_rate_5m, hash_rate_60m, shares_5m, shares_60m
        """
        try:
            url = f"{self.proxy_url}/api/workers/stats"
            params = {"worker": worker_id}

            with httpx.Client(timeout=30) as client:
                response = client.get(url, headers=self.headers, params=params)
                response.raise_for_status()

                data = response.json()

                workers = data.get("btc", {}).get("workers", {})

                if worker_id not in workers:
                    logging.debug(f"Worker {worker_id} not found in proxy response")
                    return None

                worker_data = workers[self._worker_name_to_worker_id(worker_id)]

                return {
                    "hash_rate_5m": worker_data.get("hash_rate_5m", 0.0),
                    "hash_rate_60m": worker_data.get("hash_rate_60m", 0.0),
                    "hash_rate_unit": worker_data.get("hash_rate_unit", "Gh/s"),
                    "shares_5m": worker_data.get("shares_5m", 0),
                    "shares_60m": worker_data.get("shares_60m", 0),
                    "share_value_5m": worker_data.get("share_value_5m", 0.0),
                    "share_value_60m": worker_data.get("share_value_60m", 0.0),
                    "share_value_24h": worker_data.get("share_value_24h", 0.0),
                }

        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error getting worker data: {e}")
            return None
        except Exception as e:
            logging.error(f"Error getting worker data: {e}")
            return None

    def get_all_workers_data(self, coin: str = "bitcoin") -> dict[str, dict[str, Any]]:
        """
        Get data for all workers from the proxy API.

        Args:
            coin: The coin type (default: "bitcoin")

        Returns:
            Dict mapping worker_id to worker data
        """
        try:
            url = f"{self.proxy_url}/api/workers/stats"

            with httpx.Client(timeout=30) as client:
                response = client.get(url, headers=self.headers)
                response.raise_for_status()

                data = response.json()

                workers = data.get("btc", {}).get("workers", {})

                result = {}
                for worker_id, worker_data in workers.items():
                    result[worker_id] = {
                        "hash_rate_5m": worker_data.get("hash_rate_5m", 0.0),
                        "hash_rate_60m": worker_data.get("hash_rate_60m", 0.0),
                        "hash_rate_unit": worker_data.get("hash_rate_unit", "Gh/s"),
                        "shares_5m": worker_data.get("shares_5m", 0),
                        "shares_60m": worker_data.get("shares_60m", 0),
                        "share_value_5m": worker_data.get("share_value_5m", 0.0),
                        "share_value_60m": worker_data.get("share_value_60m", 0.0),
                        "share_value_24h": worker_data.get("share_value_24h", 0.0),
                    }

                return result

        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error getting all workers data: {e}")
            return {}
        except Exception as e:
            logging.error(f"Error getting all workers data: {e}")
            return {}

    def get_workers_timerange(
        self, start_time: int, end_time: int, coin: str = "bitcoin"
    ) -> dict[str, dict[str, Any]]:
        """
        Get worker data for a specific time range.

        Args:
            start_time: Start time as unix timestamp (required)
            end_time: End time as unix timestamp (required)
            coin: The coin type (default: "bitcoin")

        Returns:
            Dict mapping worker_id to worker timerange data
        """
        try:
            url = f"{self.proxy_url}/api/workers/timerange"
            params = {"start_time": start_time, "end_time": end_time}

            with httpx.Client(timeout=30) as client:
                response = client.get(url, headers=self.headers, params=params)
                response.raise_for_status()

                data = response.json()

                workers = data.get("btc", {}).get("workers", {})

                result = {}
                for worker_id, worker_data in workers.items():
                    result[self._worker_name_to_worker_id(worker_id)] = worker_data

                return result

        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error getting workers timerange data: {e}")
            return {}
        except Exception as e:
            logging.error(f"Error getting workers timerange data: {e}")
            return {}

    def get_fpps(self, coin: str = "bitcoin") -> float:
        """
        Get FPPS (Full Pay Per Share) rate.

        For the proxy, we don't have a direct FPPS endpoint, so we return 0.0.
        The validator will use the hash price API to calculate rewards.
        """
        # Proxy doesn't provide FPPS directly
        return 0.0

    def test_connection(self) -> bool:
        """Test API connection and authentication by hitting the /health endpoint"""
        try:
            url = f"{self.proxy_url}/health"
            with httpx.Client(timeout=10) as client:
                response = client.get(url, headers=self.headers)
                response.raise_for_status()
                return True
        except Exception as e:
            logging.error(f"Failed to connect to Proxy Pool API: {str(e)}")
            return False
