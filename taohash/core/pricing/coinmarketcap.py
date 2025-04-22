import requests
from typing import Dict

from taohash.core.pricing.price import NetworkedCoinPriceAPI


class CoinMarketCapAPI(NetworkedCoinPriceAPI):
    """
    API to consume the CoinMarketCap API.
    See: https://coinmarketcap.com/api/documentation/v1/#operation/getV2CryptocurrencyQuotesLatest
    """

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("CoinMarketCap API requires an API key")
        super().__init__(api_key)
        self.query_url = (
            "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest"
        )

    def _get_price(self, coin: str, vs: str = "usd") -> float:
        """
        Get the current price of a coin.

        Args:
            coin: The id/slug of the coin (e.g., "bitcoin")
            vs: The currency to convert to (only "usd" supported currently)

        Returns:
            The current price in the specified currency

        Raises:
            ValueError: If the API request fails or currency not supported
        """
        if vs.lower() != "usd":
            raise ValueError("CoinMarketCap implementation currently only supports USD")

        prices = self._get_prices([coin], vs)
        return prices[coin]

    def _get_prices(self, coins: list[str], vs: str = "usd") -> Dict[str, float]:
        """
        Get current prices for multiple coins.

        Args:
            coins: List of coin slugs (e.g., ["bitcoin", "ethereum"])
            vs: The currency to convert to (only "usd" supported currently)

        Returns:
            Dictionary mapping coin slugs to their prices

        Raises:
            ValueError: If the API request fails or currency not supported
        """
        if vs.lower() != "usd":
            raise ValueError("CoinMarketCap implementation currently only supports USD")

        params = {"slug": ",".join(coins)}
        headers = {"X-CMC_PRO_API_KEY": self.api_key, "Accept": "application/json"}
        response = requests.get(self.query_url, params=params, headers=headers)

        if response.status_code != 200:
            raise ValueError(f"Could not get price from CoinMarketCap: {response.text}")

        data = response.json()
        result = {}
        for _, coins_data in data["data"].items():
            for coin_data in (
                coins_data if isinstance(coins_data, list) else [coins_data]
            ):
                if coin_data["slug"] in [c.lower() for c in coins]:
                    result[coin_data["slug"]] = float(
                        coin_data["quote"][vs.upper()]["price"]
                    )
        return result
