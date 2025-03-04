from typing import Optional

import abc
import cachetools
from cachetools import TTLCache

PRICE_TTL = 5 * 60  # 5 minutes

# Cache
_price_cache = TTLCache(maxsize=64, ttl=PRICE_TTL)


class CoinPriceAPIBase(metaclass=abc.ABCMeta):
    api_key: Optional[str]

    def __init__(self, api_key: Optional[str]) -> None:
        self.api_key = api_key

    @abc.abstractmethod
    def get_price(self, coin: str) -> Optional[float]:
        pass


class OfflineCoinPriceAPI(CoinPriceAPIBase):
    """
    A price API that is Offline, avoiding API calls.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        super().__init__(api_key)


class UnitCoinPriceAPI(OfflineCoinPriceAPI):
    """
    A price API that values coins at 1:1
    Useful for avoiding API calls.
    """

    def get_price(self, _: str) -> Optional[float]:
        return 1.0


class NetworkedCoinPriceAPI(CoinPriceAPIBase):
    """
    A price API that makes network requests.
    Some implementations may require an API key.
    """

    api_key: Optional[str]

    def __init__(self, api_key: Optional[str]) -> None:
        super().__init__(api_key)

    @abc.abstractmethod
    def _get_price(self, coin: str) -> float:
        pass

    def _get_prices(self, coins: list[str]) -> dict[str, float]:
        """
        Get prices for multiple coins at once.

        Args:
            coins: List of coin identifiers

        Returns:
            Dictionary mapping coin identifiers to their prices
        """
        return {coin: self._get_price(coin) for coin in coins}

    @cachetools.cached(cache=_price_cache)
    def get_price(self, coin: str) -> Optional[float]:
        try:
            return self._get_price(coin)
        except Exception as e:
            print(e)
            return None

    def get_prices(self, coins: list[str]) -> dict[str, Optional[float]]:
        """
        Get prices for multiple coins.
        Makes a single API call for all coins if any is missing from cache.
        """
        result = {}
        all_cached = True

        for coin in coins:
            # Check in cache
            cache_key = cachetools.keys.hashkey(coin)
            if cache_key in _price_cache:
                result[coin] = _price_cache[cache_key]
            else:
                all_cached = False
                break

        # If any coin was missing, fetch all prices fresh
        if not all_cached:
            try:
                latest_prices = self._get_prices(coins)
                for coin, price in latest_prices.items():
                    result[coin] = price
                    cache_key = cachetools.keys.hashkey(coin)
                    _price_cache[cache_key] = price
            except Exception as e:
                print(f"Error fetching batch prices: {e}")
                return {coin: None for coin in coins}

        return result
