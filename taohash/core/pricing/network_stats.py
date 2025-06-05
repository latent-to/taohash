"""
Bitcoin network statistics fetcher with caching.

Provides methods to fetch current Bitcoin network statistics
such as difficulty, with built-in caching to minimize API calls.
"""

import logging
import aiohttp
import asyncio
import cachetools
from cachetools import TTLCache

logger = logging.getLogger(__name__)

DIFFICULTY_TTL = 12 * 60 * 60  # 12 hours
_difficulty_cache = TTLCache(maxsize=1, ttl=DIFFICULTY_TTL)

FALLBACK_DIFFICULTY = 121_660_000_000_000  # ~121.66T fallback
API_TIMEOUT = 10  # seconds


async def _fetch_difficulty() -> float:
    """
    Fetch current Bitcoin difficulty from blockchain.info API.
    
    Returns:
        float: Current network difficulty
        
    Raises:
        Exception: If API call fails
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://blockchain.info/q/getdifficulty',
            timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)
        ) as response:
            if response.status == 200:
                difficulty_str = await response.text()
                difficulty = float(difficulty_str.strip())
                logger.info(f"Fetched Bitcoin difficulty: {difficulty:,.0f}")
                return difficulty
            else:
                raise Exception(f"API returned status {response.status}")


@cachetools.cached(cache=_difficulty_cache)
async def get_current_difficulty() -> float:
    """
    Get current Bitcoin network difficulty with caching.
    
    Returns:
        float: Current network difficulty, or fallback value if fetch fails
    """
    try:
        return await _fetch_difficulty()
    except asyncio.TimeoutError:
        logger.warning(f"Timeout fetching difficulty after {API_TIMEOUT}s")
    except Exception as e:
        logger.error(f"Error fetching difficulty: {e}")
    
    logger.warning(f"Using fallback difficulty: {FALLBACK_DIFFICULTY:,.0f}")
    return FALLBACK_DIFFICULTY