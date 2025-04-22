import requests
from typing import Optional, Dict

from .price import NetworkedCoinPriceAPI


class CoinGeckoAPI(NetworkedCoinPriceAPI):
    """
    API to consume the CoinGecko API.
    See: https://docs.coingecko.com/reference/simple-price
    """

    def __init__(self, api_key: Optional[str]) -> None:
        self.is_pro = api_key is not None
        super().__init__(api_key)

    def _get_price(self, coin: str, vs: str = "usd") -> float:
        """
        Get the current price of a coin in USD.

        Args:
            coin: The coin ID (e.g., "bitcoin")
            vs: The currency to convert to (default: "usd")

        Returns:
            The current price in the specified currency

        Raises:
            ValueError: If the API request fails
        """
        prices = self._get_prices([coin], vs)
        return prices[coin]

    def _get_prices(self, coins: list[str], vs: str = "usd") -> Dict[str, float]:
        """
        Get current prices for multiple coins.

        Args:
            coins: List of coin IDs (e.g., ["bitcoin", "ethereum"])
            vs: The currency to convert to (default: "usd")

        Returns:
            Dictionary mapping coin IDs to their prices

        Raises:
            ValueError: If the API request fails
        """
        if self.is_pro:
            url = "https://pro-api.coingecko.com/api/v3/simple/price"
            headers = {"accept": "application/json", "x-cg-pro-api-key": self.api_key}
        else:
            url = "https://api.coingecko.com/api/v3/simple/price"
            headers = {"accept": "application/json"}

        response = requests.get(
            url=url,
            headers=headers,
            params={"ids": ",".join(coins), "vs_currencies": vs},
        )

        if response.status_code != 200:
            raise ValueError(f"Could not get price from CoinGecko: {response.text}")

        result = response.json()
        prices = {}
        for coin in coins:
            if coin not in result:
                raise ValueError(f"Coin {coin} not found in CoinGecko response")
            prices[coin] = float(result[coin][vs])

        return prices
