import argparse
from typing import Optional

from taohash.core.pricing.coingecko import CoinGeckoAPI
from taohash.core.pricing.coinmarketcap import CoinMarketCapAPI
from taohash.core.pricing.hash_price import BraiinsHashPriceAPI
from taohash.core.pricing.price import (
    CoinPriceAPIBase,
    UnitCoinPriceAPI,
    HashPriceAPIBase,
)


class CoinPriceAPI:
    __CLASS_MAP: dict[str, CoinPriceAPIBase] = {
        "coingecko": CoinGeckoAPI,
        "unit": UnitCoinPriceAPI,
        "coinmarketcap": CoinMarketCapAPI,
        # Aliases
        "cmc": CoinMarketCapAPI,
        "cg": CoinGeckoAPI,
    }

    """
    Factory class for creating cryptocurrency price API instances.
    """

    def __new__(cls, method: str, api_key: Optional[str]) -> "CoinPriceAPIBase":
        """
        Create a new price API instance based on the specified method.

        Args:
            method: The pricing API to use (coingecko, unit, coinmarketcap, etc.)
            api_key: Optional API key for services that require authentication

        Returns:
            An instance of the selected price API implementation

        Raises:
            ValueError: If the specified method is not supported
        """
        if method not in cls.__CLASS_MAP:
            raise ValueError(
                f"Unknown price method: {method}. Available methods: {list(cls.__CLASS_MAP.keys())}"
            )
        return cls.__CLASS_MAP[method](api_key)

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser", _: Optional[str] = None):
        parser.add_argument(
            "--price.method",
            default="unit",
            type=str,
            choices=list(cls.__CLASS_MAP.keys()),
            help="Price API to use (default: unit)",
        )
        parser.add_argument(
            "--price.api_key",
            required=False,
            type=str,
            help="API key for the selected price API (if required)",
        )


class HashPriceAPI:
    """
    Factory class for hash price APIs.

    Creates instances of APIs that provide pricing data for mining hashrate
    across different mining pools and cryptocurrencies.
    """

    __CLASS_MAP: dict[str, HashPriceAPIBase] = {
        "braiins": BraiinsHashPriceAPI,
    }

    def __new__(cls, method: str = "braiins") -> "HashPriceAPIBase":
        """
        Create a new hash price API instance.

        Args:
            method: The hash price API to use (default: braiins)

        Returns:
            An instance of the selected hash price API implementation

        Raises:
            ValueError: If the specified method is not supported
        """
        if method not in cls.__CLASS_MAP:
            raise ValueError(
                f"Unknown hash price method: {method}. Available methods: {list(cls.__CLASS_MAP.keys())}"
            )
        return cls.__CLASS_MAP[method]()
