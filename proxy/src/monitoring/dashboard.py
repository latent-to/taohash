"""
Real-time monitoring dashboard for the mining proxy.

Provides a web interface to monitor miner connections, hashrates, and share statistics.
Includes both a visual HTML dashboard and JSON API endpoints for programmatic access.

Key features:
- Live miner statistics (hashrate, shares, difficulty)
- Pool connection status monitoring
- Per-worker performance metrics
- Optional analytics integration with ClickHouse
"""

import os
from typing import Union
from aiohttp import web

from ..utils.logger import get_logger
from .stats import StatsManager

logger = get_logger(__name__)


def create_dashboard_app(stats_manager: StatsManager, stats_db=None) -> web.Application:
    """
    Create the web application for monitoring mining proxy operations.

    Sets up routes for the dashboard UI and API endpoints. Integrates with
    optional ClickHouse analytics when database is provided.

    Args:
        stats_manager: Provides real-time miner statistics
        stats_db: Optional ClickHouse connection for historical analytics

    Returns:
        Configured aiohttp application with dashboard and API routes
    """
    app = web.Application()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up two levels: monitoring -> src -> project root
    src_dir = os.path.dirname(base_dir)
    project_root = os.path.dirname(src_dir)
    static_dir = os.path.join(project_root, "static")

    pool_info: dict[str, Union[str, int]] = {
        "url": "Not connected",
        "user": "N/A",
        "connected_since": 0,
    }

    async def index(request: web.Request) -> web.Response:
        """
        Serve the main dashboard interface.

        Returns an HTML page with real-time charts and statistics
        for monitoring miner performance and pool connectivity.
        """
        index_path = os.path.join(static_dir, "index.html")
        return web.FileResponse(index_path)

    async def api_stats(request: web.Request) -> web.Response:
        """
        Return real-time mining statistics for all connected workers.

        Response includes per-miner data:
        - Current hashrate (5m/60m/24h averages)
        - Accepted/rejected share counts
        - Current difficulty
        - Connection uptime
        - Pool assignments

        Returns:
            JSON object with miner addresses as keys
        """
        stats = stats_manager.get_all_stats()
        return web.json_response(stats)

    async def api_pool_info(request: web.Request) -> web.Response:
        """
        Return current mining pool configuration.

        Reads pool settings from config.toml and returns:
        - Pool URL (host:port)
        - Mining username/wallet address
        - Connection timestamp

        Used by dashboard to display pool connectivity status.

        Returns:
            JSON with {url, user, connected_since}
        """
        try:
            import toml

            config_dir = os.path.join(project_root, "config")
            config_path = os.path.join(config_dir, "config.toml")

            if os.path.exists(config_path):
                data = toml.load(config_path)

                if "pool" in data:
                    pool = data["pool"]
                    
                    pool_info["url"] = (
                        f"{pool.get('host', 'unknown')}:{pool.get('port', '0')}"
                    )
                    pool_info["user"] = pool.get("user", "N/A")
        except Exception as e:
            logger.error(f"Error reading pool info: {e}")

        return web.json_response(pool_info)

    app.router.add_static("/static/", static_dir)

    app.add_routes(
        [
            web.get("/", index),
            web.get("/api/stats", api_stats),
            web.get("/api/pool", api_pool_info),
        ]
    )
    
    # Add analytics routes if database is available
    if stats_db:
        from .analytics_api import create_analytics_routes
        create_analytics_routes(app, stats_db)

    return app
