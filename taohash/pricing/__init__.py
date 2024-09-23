from typing import Dict, Optional
import argparse

from .price import CoinPriceAPIBase, UnitCoinPriceAPI
from .coingecko import CoinGeckoAPI


__CLASS_MAP: Dict[str, CoinPriceAPIBase] = {
    "cg": CoinGeckoAPI,
    "coingecko": CoinGeckoAPI,
    "unit": UnitCoinPriceAPI,
}


class CoinPriceAPI:
    """
    Factory class
    """

    def __new__(cls, method: str, api_key: Optional[str]) -> "CoinPriceAPIBase":
        return __CLASS_MAP[method](api_key)

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser", _: Optional[str] = None):
        parser.add_argument(
            "--price.method",
            default="unit",
            type=str,
            choices=list(__CLASS_MAP.keys()),
        )
        parser.add_argument(
            "--price.api_key",
            required=False,
            type=str,
        )
