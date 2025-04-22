from typing import Dict, Optional
import argparse

from taohash.core.pricing.price import CoinPriceAPIBase, UnitCoinPriceAPI, HashPriceAPIBase
from taohash.core.pricing.coingecko import CoinGeckoAPI
from taohash.core.pricing.coinmarketcap import CoinMarketCapAPI
from taohash.core.pricing.hash_price import BraiinsHashPriceAPI


class CoinPriceAPI:
    __CLASS_MAP: Dict[str, CoinPriceAPIBase] = {
        "coingecko": CoinGeckoAPI,
        "unit": UnitCoinPriceAPI,
        "coinmarketcap": CoinMarketCapAPI,
        # Aliases
        "cmc": CoinMarketCapAPI,
        "cg": CoinGeckoAPI,
    }

    """
    Factory class
    """

    def __new__(cls, method: str, api_key: Optional[str]) -> "CoinPriceAPIBase":
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
    """Factory class for hash price APIs"""
    
    __CLASS_MAP: Dict[str, HashPriceAPIBase] = {
        "braiins": BraiinsHashPriceAPI,
    }
    
    def __new__(cls, method: str = "braiins") -> "HashPriceAPIBase":
        if method not in cls.__CLASS_MAP:
            raise ValueError(
                f"Unknown hash price method: {method}. Available methods: {list(cls.__CLASS_MAP.keys())}"
            )
        return cls.__CLASS_MAP[method]()
