import requests    

from .price import NetworkedCoinPriceAPI

class CoinGeckoAPI(NetworkedCoinPriceAPI):
    """
    This price API uses the CoinGecko API.
    See: https://docs.coingecko.com/reference/simple-price
    """
    __url: str = "https://pro-api.coingecko.com/api/v3/simple/price"
     
    def _get_price(self, coin: str, vs: str = "usd") -> float:
        response = requests.get(
            url=self.__url,
            headers = {
                "accept": "application/json",
                "x-cg-pro-api-key": self.api_key
            },
            params = {
                "ids": coin,
                "vs_currencies": vs
            },
        )

        if response.status_code != 200:
            raise ValueError("Could not get price from CoinGecko")

        result = response.json()
        price = result[coin][vs]

        return price

