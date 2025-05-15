"""
Web dashboard for mining proxy statistics.

This module provides a web interface for monitoring the mining proxy's status.
It includes both a human-readable HTML dashboard and a machine-readable JSON API
endpoint for retrieving real-time statistics about connected miners.
"""

import os
import time
from typing import Union
from aiohttp import web

from .logger import get_logger
from .stats import StatsManager

logger = get_logger(__name__)


def create_dashboard_app(stats_manager: StatsManager) -> web.Application:
    """
    Create and configure the aiohttp web application for the dashboard.

    Sets up the routing table and request handlers for both the HTML
    dashboard and the JSON API endpoint.

    Args:
        stats_manager (StatsManager): The central statistics manager instance

    Returns:
        web.Application: Configured aiohttp web application
    """
    app = web.Application()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(base_dir)
    static_dir = os.path.join(parent_dir, "static")

    pool_info: dict[str, Union[str, int]] = {
        "url": "Not connected",
        "user": "N/A",
        "connected_since": 0,
    }

    async def index(request: web.Request) -> web.Response:
        """
        Handle GET / - serve the HTML dashboard.

        Args:
            request (web.Request): HTTP request object

        Returns:
            web.Response: HTML response with the dashboard
        """
        index_path = os.path.join(static_dir, "index.html")
        return web.FileResponse(index_path)

    async def api_stats(request: web.Request) -> web.Response:
        """
        Handle GET /api/stats - return JSON statistics.

        Provides a simple JSON API for programmatic access to the current
        mining statistics for all connected miners.

        Args:
            request (web.Request): HTTP request object

        Returns:
            web.Response: JSON response with statistics data
        """
        stats = stats_manager.get_all_stats()
        return web.json_response(stats)

    async def api_pool_info(request: web.Request) -> web.Response:
        """
        Handle GET /api/pool - return current pool information.

        Provides information about the currently configured mining pool,
        including URL, username, and connection time.

        Args:
            request (web.Request): HTTP request object

        Returns:
            web.Response: JSON response with pool information
        """
        try:
            import toml

            config_dir = os.path.join(parent_dir, "config")
            config_path = os.path.join(config_dir, "config.toml")

            if os.path.exists(config_path):
                data = toml.load(config_path)

                if "pool" in data:
                    pool = data["pool"]
                    if not pool_info["connected_since"]:
                        pool_info["connected_since"] = int(time.time())

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

    return app
