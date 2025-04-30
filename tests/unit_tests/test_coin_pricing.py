import pytest
from unittest.mock import patch
import responses

from taohash.core.pricing.coingecko import CoinGeckoAPI
from taohash.core.pricing.coinmarketcap import CoinMarketCapAPI
from taohash.core.pricing.price import UnitCoinPriceAPI

# Test data
MOCK_COINGECKO_RESPONSE = {
    "bitcoin": {"usd": 50000.0},
    "ethereum": {"usd": 3000.0},
    "solana": {"usd": 100.0},
}

MOCK_CMC_RESPONSE = {
    "status": {"error_code": 0},
    "data": {
        "1": {"slug": "bitcoin", "quote": {"USD": {"price": 50000.0}}},
        "1027": {"slug": "ethereum", "quote": {"USD": {"price": 3000.0}}},
    },
}


# Unit Price API Tests
class TestUnitPriceAPI:
    def setup_method(self):
        self.api = UnitCoinPriceAPI()

    def test_get_price_always_returns_one(self):
        assert self.api.get_price("any_coin") == 1.0
        assert self.api.get_price("bitcoin") == 1.0
        assert self.api.get_price("nonexistent") == 1.0


# CoinGecko Free API Tests
class TestCoinGeckoAPI:
    def setup_method(self):
        self.api = CoinGeckoAPI(api_key=None)

    @responses.activate
    def test_get_single_price(self):
        # Mock the API response
        responses.add(
            responses.GET,
            "https://api.coingecko.com/api/v3/simple/price",
            json={"bitcoin": {"usd": 50000.0}},
            status=200,
        )

        price = self.api.get_price("bitcoin")
        assert price == 50000.0

    @responses.activate
    def test_get_multiple_prices(self):
        # Mock the API response
        responses.add(
            responses.GET,
            "https://api.coingecko.com/api/v3/simple/price",
            json=MOCK_COINGECKO_RESPONSE,
            status=200,
        )

        prices = self.api.get_prices(["bitcoin", "ethereum", "solana"])
        assert prices["bitcoin"] == 50000.0
        assert prices["ethereum"] == 3000.0
        assert prices["solana"] == 100.0

    @responses.activate
    def test_api_error_handling(self):
        # Mock an API error
        responses.add(
            responses.GET,
            "https://api.coingecko.com/api/v3/simple/price",
            json={"error": "API error"},
            status=400,
        )

        price = self.api.get_price("bitcoin")
        assert price is None

    def test_cache_functionality(self):
        with patch.object(self.api, "_get_price") as mock_get_price:
            mock_get_price.return_value = 50000.0

            # First call should hit the API
            first_price = self.api.get_price("bitcoin")
            assert first_price == 50000.0
            mock_get_price.assert_called_once()

            # Second call should use cache
            second_price = self.api.get_price("bitcoin")
            assert second_price == 50000.0
            mock_get_price.assert_called_once()  # Still only called once


# CoinMarketCap API Tests
class TestCoinMarketCapAPI:
    def setup_method(self):
        self.api = CoinMarketCapAPI(api_key="test_key")

    @responses.activate
    def test_get_single_price(self):
        # Mock the API response
        responses.add(
            responses.GET,
            "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest",
            json=MOCK_CMC_RESPONSE,
            status=200,
        )

        price = self.api.get_price("bitcoin")
        assert price == 50000.0

    @responses.activate
    def test_get_multiple_prices(self):
        # Mock the API response
        responses.add(
            responses.GET,
            "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest",
            json=MOCK_CMC_RESPONSE,
            status=200,
        )

        prices = self.api.get_prices(["bitcoin", "ethereum"])
        assert prices["bitcoin"] == 50000.0
        assert prices["ethereum"] == 3000.0

    def test_api_key_required(self):
        with pytest.raises(ValueError, match="CoinMarketCap API requires an API key"):
            CoinMarketCapAPI(api_key="")

    @responses.activate
    def test_api_error_handling(self):
        # Mock an API error
        responses.add(
            responses.GET,
            "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest",
            json={"error": "API error"},
            status=400,
        )

        price = self.api.get_price("bitcoin")
        assert price is None

    def test_cache_functionality(self):
        with patch.object(self.api, "_get_price") as mock_get_price:
            mock_get_price.return_value = 50000.0

            # First call should hit the API
            first_price = self.api.get_price("bitcoin")
            assert first_price == 50000.0
            mock_get_price.assert_called_once()

            # Second call should use cache
            second_price = self.api.get_price("bitcoin")
            assert second_price == 50000.0
            mock_get_price.assert_called_once()  # Still only called once
