from typing import Optional
from cachetools import TTLCache, cached
from taohash.pool.pool import PoolBase
from taohash.pricing.price import CoinPriceAPIBase


HASH_PRICE_TTL = 5 * 60  # 5 minutes
hash_price_cache = TTLCache(maxsize=64, ttl=HASH_PRICE_TTL)

SHARES_PER_TH_PER_SECOND = 1
SECONDS_PER_DAY = 86400


class HashPriceCalculator:
    """Calculator for mining hash price based on pool FPPS and coin price"""

    def __init__(self, pool_api: PoolBase, price_api: CoinPriceAPIBase) -> None:
        self.pool_api = pool_api
        self.price_api = price_api

    @cached(cache=hash_price_cache)
    def get_hash_price(self, coin: str = "bitcoin", vs: str = "usd") -> Optional[float]:
        """Calculate hash price in USD/TH/day

        Args:
            coin: The coin to calculate hash price for (default: bitcoin)
            vs: The currency to price in (default: usd)

        Returns:
            Hash price in USD/TH/day or None if calculation fails
        """
        try:
            coin_price = self.price_api.get_price(coin, vs)
            if coin_price is None:
                return None

            fpps = self.pool_api.get_fpps(coin)

            # FPPS (BTC/share) * shares/TH/s * seconds/day * USD/BTC
            hash_price = fpps * SHARES_PER_TH_PER_SECOND * SECONDS_PER_DAY * coin_price

            return hash_price

        except Exception as e:
            print(f"Error calculating hash price: {e}")
            return None

    def get_hash_price_per_hour(
        self, coin: str = "bitcoin", vs: str = "usd"
    ) -> Optional[float]:
        """Get hash price per hour"""
        daily_price = self.get_hash_price(coin, vs)
        if daily_price is None:
            return None
        return daily_price / 24
