from typing import Optional

import abc
import cachetools
from cachetools import TTLCache

PRICE_TTL = 5 * 60  # 5 minutes

# Cache
_price_cache = TTLCache(maxsize=64, ttl=PRICE_TTL)


class CoinPriceAPIBase(metaclass=abc.ABCMeta):
    """
    Abstract base class for cryptocurrency price APIs.

    Defines the interface for retrieving coin prices from
    various data sources, both online and offline.
    """

    api_key: Optional[str]

    def __init__(self, api_key: Optional[str]) -> None:
        self.api_key = api_key

    @abc.abstractmethod
    def get_price(self, coin: str) -> Optional[float]:
        """
        Get the current price of a coin in USD.

        Args:
            coin: Symbol or identifier for the cryptocurrency

        Returns:
            The price in USD or None if unavailable
        """
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
        """
        Get a coin's price with caching.

        Args:
            coin: Symbol or identifier for the cryptocurrency

        Returns:
            The current price in USD, or None if fetch fails
        """
        try:
            return self._get_price(coin)
        except Exception as e:
            print(e)
            return None

    def get_prices(self, coins: list[str]) -> dict[str, Optional[float]]:
        """
        Get prices for multiple coins at once.

        Args:
            coins: List of coin identifiers

        Returns:
            Dictionary mapping coin identifiers to their prices
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


class HashPriceAPIBase(metaclass=abc.ABCMeta):
    """
    Abstract base class for mining hashrate price APIs.

    Used to retrieve current profitability rates for
    different mining algorithms and cryptocurrencies.
    """

    @abc.abstractmethod
    def get_hash_price(self, coin: str) -> Optional[float]:
        """
        Get the current hash price in USD/TH/day for a coin.

        Args:
            coin: Symbol or identifier for the cryptocurrency

        Returns:
            The current hash price or None if unavailable
        """
        pass
