from typing import Optional

import cachetools
import requests
from backoff import expo, on_exception
from cachetools import TTLCache
from ratelimit import RateLimitException, limits

from taohash.core.pricing.price import HashPriceAPIBase

HASH_PRICE_TTL = 30 * 60  # 30 minutes
_hash_price_cache = TTLCache(maxsize=64, ttl=HASH_PRICE_TTL)


class BraiinsHashPriceAPI(HashPriceAPIBase):
    """
    Hash price API implementation using Braiins Pool insights
    See: https://insights.braiins.com/api/v1.0/hashrate-stats
    """

    def __init__(self) -> None:
        pass

    @on_exception(expo, RateLimitException, max_tries=8)
    @limits(calls=1, period=10)  # rate limit once per 10s
    def get_hashrate_stats(self) -> dict:
        """
        Get current network hashrate statistics from Braiins Pool for BTC.
        Raises:
            ValueError: If the API request fails
        """
        url = "https://insights.braiins.com/api/v1.0/hashrate-stats"

        response = requests.get(
            url=url,
            headers={
                "accept": "application/json",
            },
            timeout=20,
        )

        if response.status_code != 200:
            raise ValueError(
                f"Could not get hashrate stats from Braiins: {response.text}"
            )

        return response.json()

    @cachetools.cached(cache=_hash_price_cache)
    def get_hash_price(self, coin: str) -> Optional[float]:
        """
        Get the current hash price in USD/TH/day from Braiins Pool insights

        Returns:
            float: Current hash price or None if unavailable
        """
        try:
            stats = self.get_hashrate_stats()
            return float(stats["hash_price"])
        except Exception as e:
            print(f"Error fetching hash price from Braiins: {e}")
            return None

    @cachetools.cached(cache=_hash_price_cache)
    def get_hash_value(self) -> Optional[float]:
        """
        Get the current hash value in BTC/TH/day from Braiins Pool insights

        Returns:
            float: Current hash value in BTC/TH/day or None if unavailable
        """
        try:
            stats = self.get_hashrate_stats()
            return float(stats.get("hash_value"))
        except Exception as e:
            print(f"Error fetching hash value from Braiins: {e}")
            return None
