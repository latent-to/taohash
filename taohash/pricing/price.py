from typing import Optional

import abc
import cachetools

PRICE_TTL = 5 * 60  # 5min

class CoinPriceAPIBase(metaclass=abc.ABCMeta):
    api_key: Optional[str]

    def __init__(self, api_key: Optional[str]) -> None:
        self.api_key = api_key

    @abc.abstractmethod
    def get_price(self, coin: str) -> float:
        pass


class OfflineCoinPriceAPI(CoinPriceAPIBase):
    """
    A price API that is Offline, avoiding API calls.
    """

    def __init__(self, _) -> None:
        # ignores the api_key; not needed
        pass


class UnitCoinPriceAPI(OfflineCoinPriceAPI):
    """
    A price API that values coins at 1:1
    Useful for avoiding API calls.
    """

    def get_hash_price(self, _: str) -> float:
        return 1.0


class NetworkedCoinPriceAPI(CoinPriceAPIBase):
    api_key: str

    def __init__(self, api_key: Optional[str]) -> None:
        if api_key is None:
            raise ValueError("This Price API requires an API Key")

        self.api_key = api_key

    @abc.abstractmethod
    def _get_price(self, coin: str) -> float:
        pass

    @cachetools.func.ttl_cache(maxsize=64, ttl=PRICE_TTL)
    def get_price(self, coin: str) -> float:
        try:
            return self._get_price(coin)
        except Exception as e:
            print(e)
            # Fallback to 1:1
            return 1.0

