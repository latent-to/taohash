from typing import Dict, Optional

import abc
import argparse
import requests
import cachetools

HASHPRICE_TTL = 5 * 60  # 5min


class HashPriceAPI(metaclass=abc.ABCMeta):
    api_key: Optional[str]

    def __init__(self, api_key: Optional[str]) -> None:
        self.api_key = api_key

    def __new__(cls, method: str, api_key: Optional[str]) -> "HashPriceAPI":
        return __ENUM_MAP[method](api_key)

    @abc.abstractmethod
    def get_hash_price(self, coin: str) -> float:
        pass

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser", _: Optional[str] = None):
        parser.add_argument(
            "--hashprice.method",
            "--hp.method",
            "--price.method",
            default="unit",
            type=str,
            choices=list(__ENUM_MAP.keys()),
        )
        parser.add_argument(
            "--hashprice.api_key",
            "--hp.api_key",
            "--price.api_key",
            required=False,
            type=str,
        )


class OfflineHashPriceAPI(HashPriceAPI):
    """
    A hashprice API that is Offline, avoiding API calls.
    """

    def __init__(self, _) -> None:
        # ignores the api_key; not needed
        pass


class UnitHashPriceAPI(OfflineHashPriceAPI):
    """
    A hashprice API that values hashrate at 1:1
    Useful for avoiding API calls.
    """

    def get_hash_price(self, _: str) -> float:
        return 1.0


class NetworkedHashPriceAPI(HashPriceAPI):
    api_key: str

    def __init__(self, api_key: Optional[str]) -> None:
        if api_key is None:
            raise ValueError("This Hash Price API requires an API Key")

        self.api_key = api_key

    @abc.abstractmethod
    def _get_hash_price(self, coin: str) -> float:
        pass

    @cachetools.func.ttl_cache(maxsize=64, ttl=HASHPRICE_TTL)
    def get_hash_price(self, coin: str) -> float:
        return self._get_hash_price(coin)


class HashRateIndexAPI(NetworkedHashPriceAPI):
    """
    A Hash Price API offered by HashRateIndex.com
    See: https://api.hashrateindex.com/v1/hashrateindex/docs#/

    Note: This supports BTC hashprice ONLY
    """

    api_key: str
    __url = "https://api.hashrateindex.com/v1/hashrateindex/hashprice"

    def _get_hash_price(self, coin: str) -> float:
        if coin != "bitcoin":
            raise ValueError("HashRateIndex only supports bitcoin's hashprice")

        try:
            response = requests.get(
                url=self.__url,
                headers={"X-Hi-Api-Key": self.api_key},
                params={
                    "span": "1D",
                    "bucket": "5m",
                    "currency": "USD",
                    "hashunit": "THS",
                },
            )

            result = response.json()
            return result["data"]["price"]
        except Exception as e:
            print(e)


__ENUM_MAP: Dict[str, HashPriceAPI] = {
    "hashrateindex": HashRateIndexAPI,
    "unit": UnitHashPriceAPI,
}
