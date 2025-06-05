"""
Web dashboard for mining proxy statistics.

This module provides a web interface for monitoring the mining proxy's status.
It includes both a human-readable HTML dashboard and a machine-readable JSON API
endpoint for retrieving real-time statistics about connected miners.
"""

import os
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


    async def api_pools_info(request: web.Request) -> web.Response:
        """
        Handle GET /api/pools - return all mining pools with configuration and live statistics.


        Returns:
            JSON with pool names as keys, each containing:
            - host, port, proxy_port from config
            - connected_miners count
            - total_hashrate sum
            - total accepted/rejected shares
        """
        try:
            import toml

            config_dir = os.path.join(parent_dir, "config")
            config_path = os.path.join(config_dir, "config.toml")
            
            pools_data = {}
            
            if os.path.exists(config_path):
                data = toml.load(config_path)
                if "pools" in data:
                    for pool_name, pool_config in data["pools"].items():
                        pools_data[pool_name] = {
                            "host": pool_config.get("host", "unknown"),
                            "port": pool_config.get("port", 0),
                            "proxy_port": pool_config.get("proxy_port", 0),
                            "user": pool_config.get("user", "unknown"),
                            "connected_miners": 0,
                            "total_hashrate": 0.0,
                            "total_accepted": 0,
                            "total_rejected": 0,
                        }
            
            # Aggregate miner statistics by pool
            miner_stats = stats_manager.get_all_stats()
            for miner in miner_stats:
                pool_name = miner.get("pool", "unknown")
                if pool_name in pools_data:
                    pools_data[pool_name]["connected_miners"] += 1
                    pools_data[pool_name]["total_hashrate"] += miner.get("hashrate", 0)
                    pools_data[pool_name]["total_accepted"] += miner.get("accepted", 0)
                    pools_data[pool_name]["total_rejected"] += miner.get("rejected", 0)
            
            return web.json_response(pools_data)
            
        except Exception as e:
            logger.error(f"Error reading pools info: {e}")
            return web.json_response({})

    app.router.add_static("/static/", static_dir)

    app.add_routes(
        [
            web.get("/", index),
            web.get("/api/stats", api_stats),
            web.get("/api/pools", api_pools_info),
        ]
    )

    return app
