"""
Cryptocurrency network statistics fetcher with caching.

Provides methods to fetch current network statistics (difficulty)
for various coins, with caching to minimize API calls.
"""

import requests
from bittensor import logging
from cachetools import TTLCache
from typing import Any


DIFFICULTY_TTL = 1 * 60 * 60  # 1 hour
_difficulty_cache = TTLCache(maxsize=10, ttl=DIFFICULTY_TTL)

API_TIMEOUT = 10  # seconds

DIFFICULTY_APIS: dict[str, dict[str, Any]] = {
    "btc": {
        "url": "https://blockchain.info/q/getdifficulty",
        "response_type": "text",
        "fallback": 152_000_000_000_000,  # ~152T (as of Nov 2024)
    },
    "bch": {
        "url": "https://api.fullstack.cash/v5/blockchain/getDifficulty",
        "response_type": "json",
        "fallback": 740_000_000_000,  # ~740B (as of Nov 2024)
    },
}


def _fetch_difficulty(coin: str = "btc") -> float:
    """
    Fetch current difficulty for specified cryptocurrency.

    Args:
        coin: Cryptocurrency identifier (e.g., "btc", "bch")

    Returns:
        float: Current network difficulty

    Raises:
        Exception: If API call fails or coin not supported
    """
    if coin not in DIFFICULTY_APIS:
        raise ValueError(f"Unsupported coin: {coin}")

    config = DIFFICULTY_APIS[coin]

    response = requests.get(config["url"], timeout=API_TIMEOUT)
    if response.status_code == 200:
        if config["response_type"] == "text":
            difficulty = float(response.text.strip())
        elif config["response_type"] == "json":
            difficulty = float(response.json())
        else:
            raise ValueError(f"Unknown response type: {config['response_type']}")

        logging.info(f"Fetched {coin.upper()} difficulty: {difficulty:,.0f}")
        return difficulty
    else:
        raise Exception(f"API returned status {response.status_code}")


def get_current_difficulty(coin: str = "btc") -> float:
    """
    Get current network difficulty with caching for specified cryptocurrency.

    Args:
        coin: Cryptocurrency identifier (e.g., "btc", "bch"). Defaults to "btc".

    Returns:
        float: Current network difficulty, or fallback value if fetch fails
    """
    cache_key = f"difficulty_{coin}"

    if cache_key in _difficulty_cache:
        return _difficulty_cache[cache_key]

    try:
        difficulty = _fetch_difficulty(coin)
        _difficulty_cache[cache_key] = difficulty
        return difficulty

    except requests.Timeout:
        logging.warning(
            f"Timeout fetching {coin.upper()} difficulty after {API_TIMEOUT}s"
        )
    except Exception as e:
        logging.error(f"Error fetching {coin.upper()} difficulty: {e}")

    fallback = DIFFICULTY_APIS.get(coin).get("fallback")
    logging.warning(f"Using fallback {coin.upper()} difficulty: {fallback:,.0f}")
    return fallback
