from typing import Dict, Type
from enum import Enum
import argparse

from .price import CoinPriceAPIBase, UnitCoinPriceAPI
from .coingecko import CoinGeckoAPI
from .coinmarketcap import CoinMarketCapAPI


class PriceAPIMethod(Enum):
    CoinGecko = "coingecko"
    CoinMarketCap = "coinmarketcap"
    UnitCoinPrice = "unitcoinprice"


_CLASS_MAP: Dict[PriceAPIMethod, Type[CoinPriceAPIBase]] = {
    PriceAPIMethod.CoinGecko: CoinGeckoAPI,
    PriceAPIMethod.CoinMarketCap: CoinMarketCapAPI,
    PriceAPIMethod.UnitCoinPrice: UnitCoinPriceAPI,
}


class CoinPriceAPI:
    def __new__(cls, method: PriceAPIMethod, api_key: str) -> CoinPriceAPIBase:
        if method not in _CLASS_MAP:
            raise ValueError(f"Unknown price API method: {method}")

        api_class = _CLASS_MAP[method]
        return api_class(api_key)

    @classmethod
    def add_args(cls, parser: argparse.ArgumentParser):
        price_group = parser.add_argument_group("price")
        price_group.add_argument(
            "--price.method",
            type=PriceAPIMethod,
            choices=list(PriceAPIMethod),
            default=PriceAPIMethod.CoinGecko,
            help="Price API to use",
        )
        price_group.add_argument(
            "--price.api_key",
            type=str,
            default="",  # CoinGecko offers basic usage without an API key
            help="API key for price service",
        )
