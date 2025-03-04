import pytest
import os
import time
from typing import Generator

from taohash.pricing.coingecko import CoinGeckoAPI
from taohash.pricing.coinmarketcap import CoinMarketCapAPI

DEFAULT_CMC_API_KEY = "ae51ce7e-62f3-4332-973c-4eeeb068dde2"

# Skip all tests if SKIP_INTEGRATION_TESTS is set
pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_INTEGRATION_TESTS") == "1",
    reason="Integration tests skipped. Set SKIP_INTEGRATION_TESTS=0 to run.",
)


@pytest.fixture(scope="module")
def cmc_api() -> Generator[CoinMarketCapAPI, None, None]:
    """Fixture for CoinMarketCap API"""
    api_key = os.getenv("COINMARKETCAP_API_KEY", DEFAULT_CMC_API_KEY)
    if not api_key:
        pytest.skip("COINMARKETCAP_API_KEY not set")
    api = CoinMarketCapAPI(api_key=api_key)
    yield api
    time.sleep(1)


@pytest.fixture(scope="module")
def coingecko_free_api() -> Generator[CoinGeckoAPI, None, None]:
    """Fixture for CoinGecko Free API"""
    api = CoinGeckoAPI(api_key=None)
    yield api
    time.sleep(1)


class TestCoinMarketCapIntegration:
    """Integration tests for CoinMarketCap API"""

    def test_get_bitcoin_price(self, cmc_api: CoinMarketCapAPI):
        price = cmc_api.get_price("bitcoin")
        assert price is not None
        assert isinstance(price, float)
        assert price > 0

    def test_get_multiple_prices(self, cmc_api: CoinMarketCapAPI):
        coins = ["bitcoin", "ethereum", "bittensor"]
        prices = cmc_api.get_prices(coins)

        assert len(prices) == 3
        for coin in coins:
            assert coin in prices
            assert isinstance(prices[coin], float)
            assert prices[coin] > 0

    def test_cache_works(self, cmc_api: CoinMarketCapAPI):
        # First call
        start_time = time.time()
        first_price = cmc_api.get_price("bittensor")
        first_call_time = time.time() - start_time

        # Second call (should be from cache)
        start_time = time.time()
        second_price = cmc_api.get_price("bittensor")
        second_call_time = time.time() - start_time

        assert first_price == second_price
        assert second_call_time < first_call_time  # Cache should be faster

    def test_invalid_coin(self, cmc_api: CoinMarketCapAPI):
        price = cmc_api.get_price("not_a_real_coin_name")
        assert price is None


class TestCoinGeckoIntegration:
    """Integration tests for CoinGecko Free API"""

    def test_get_bitcoin_price(self, coingecko_free_api: CoinGeckoAPI):
        price = coingecko_free_api.get_price("bitcoin")
        assert price is not None
        assert isinstance(price, float)
        assert price > 0

    def test_get_multiple_prices(self, coingecko_free_api: CoinGeckoAPI):
        coins = ["bitcoin", "ethereum", "solana"]
        prices = coingecko_free_api.get_prices(coins)

        assert len(prices) == 3
        for coin in coins:
            assert coin in prices
            assert isinstance(prices[coin], float)
            assert prices[coin] > 0

    def test_cache_works(self, coingecko_free_api: CoinGeckoAPI):
        # First call
        start_time = time.time()
        first_price = coingecko_free_api.get_price("bittensor")
        first_call_time = time.time() - start_time

        # Second call (should be from cache)
        start_time = time.time()
        second_price = coingecko_free_api.get_price("bittensor")
        second_call_time = time.time() - start_time

        assert first_price == second_price
        assert second_call_time < first_call_time  # Cache should be faster

    def test_invalid_coin(self, coingecko_free_api: CoinGeckoAPI):
        price = coingecko_free_api.get_price("not_a_real_coin_name")
        assert price is None


def test_price_correlation(cmc_api: CoinMarketCapAPI, coingecko_free_api: CoinGeckoAPI):
    """Test that prices from different APIs are reasonably close"""
    coins = ["bitcoin", "ethereum"]

    cmc_prices = cmc_api.get_prices(coins)
    coingecko_prices = coingecko_free_api.get_prices(coins)

    for coin in coins:
        cmc_price = cmc_prices[coin]
        coingecko_price = coingecko_prices[coin]

        # Prices should be within 1% of each other
        price_diff_percent = abs(cmc_price - coingecko_price) / cmc_price * 100
        assert price_diff_percent < 1, f"Price difference too large for {coin}"
