import asyncio
import os
import sys
from typing import Any

import toml
from aiohttp import web

from .dashboard import create_dashboard_app
from .miner_session import MinerSession
from .stats import StatsManager
from .db import StatsDB
from .logger import get_logger
from .constants import (
    RELOAD_API_PORT,
    RELOAD_API_HOST,
    INTERNAL_PROXY_PORT,
    INTERNAL_DASHBOARD_PORT,
    CONFIG_PATH,
)

logger = get_logger(__name__)

config: dict = {}
active_sessions: set[MinerSession] = set()
stats_manager = StatsManager()


def load_config(path: str = CONFIG_PATH) -> dict:
    with open(path, "r") as f:
        data = toml.load(f)

    return {
        "pool_host": data["pool"]["host"],
        "pool_port": data["pool"]["port"],
        "pool_user": data["pool"]["user"],
        "pool_pass": data["pool"]["pass"],
    }


def update_config(path: str = CONFIG_PATH) -> bool:
    """
    Reload TOML → swap in new `config` → schedule teardown of sessions in the background.

    This function applies config changes immediately and schedules session closures
    to happen in the background, so it doesn't block waiting for connections to close.
    """
    new_conf = load_config(path)

    config.clear()
    config.update(new_conf)
    logger.info(f"🔄 Configuration reloaded: {config}")

    sessions = list(active_sessions)
    active_sessions.clear()

    async def close_sessions_background() -> None:
        for sess in sessions:
            try:
                sess.miner_writer.transport.abort()
                if hasattr(sess, "pool_session") and sess.pool_session:
                    sess.pool_session.writer.transport.abort()
            except Exception as e:
                logger.error(f"⚠️ Error closing session: {e}")
        logger.info(
            f"🔌 Scheduled closure of {len(sessions)} sessions. New connections will use updated config."
        )

    asyncio.create_task(close_sessions_background())

    return True


async def handle_reload_request(request: web.Request) -> web.Response:
    logger.info(f"🔁 Received reload from {request.remote}")
    try:
        success = update_config()
        if success:
            return web.Response(text="Reload scheduled")
        else:
            return web.Response(status=500, text="Failed to update config")
    except Exception as e:
        logger.error(f"Failed to reload configuration: {e}")
        return web.Response(status=500, text=str(e))


async def handle_new_miner(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    """
    Fired on each TCP connection from a miner.  We:
      1) Instantiate a MinerSession with the *current* pool config
      2) Track it in active_sessions
      3) Schedule its run() as a background task
      4) On completion, clean up stats + the session set
    """
    miner_address = writer.get_extra_info("peername")
    logger.info(f"➕ Miner connected: {miner_address}")

    session = MinerSession(
        reader,
        writer,
        config["pool_host"],
        config["pool_port"],
        config["pool_user"],
        config["pool_pass"],
        stats_manager,
    )

    active_sessions.add(session)
    task = asyncio.create_task(session.run())

    def _on_done(_: Any) -> None:
        active_sessions.discard(session)
        stats_manager.unregister_miner(miner_address)
        logger.info(f"Miner disconnected: {miner_address}")

    task.add_done_callback(_on_done)


async def start_reload_api() -> web.TCPSite:
    """Start a separate web server just for handling reload requests (internal use only)"""
    app = web.Application()
    app.router.add_post("/api/reload", handle_reload_request)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, RELOAD_API_HOST, RELOAD_API_PORT)
    await site.start()

    logger.info(
        f"Internal reload API running on http://{RELOAD_API_HOST}:{RELOAD_API_PORT}/api/reload"
    )
    return site


async def main() -> None:
    if os.path.exists(CONFIG_PATH):
        config_path = CONFIG_PATH
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        config_path = os.path.join(parent_dir, "config", "config.toml")
        if not os.path.exists(config_path):
            logger.error(f"❌ Config file not found at {config_path}")
            sys.exit(1)

    update_config(config_path)

    config_dir = os.path.dirname(config_path)
    db_path = os.path.join(config_dir, "stats.db")
    stats_db = StatsDB(db_path)
    await stats_db.init()
    stats_manager.db = stats_db

    logger.info("🚀 Starting with configuration:")
    logger.info(f"  Pool: {config['pool_host']}:{config['pool_port']}")
    logger.info(f"  User: {config['pool_user']}")
    logger.info(f"  Proxy listening on: 0.0.0.0:{INTERNAL_PROXY_PORT}")
    logger.info(f"  Dashboard on: 0.0.0.0:{INTERNAL_DASHBOARD_PORT}")
    logger.info(f"  Reload API on: {RELOAD_API_HOST}:{RELOAD_API_PORT} (internal only)")

    # Internal reload API
    await start_reload_api()

    # Stratum proxy TCP server (miners connect here)
    server = await asyncio.start_server(
        handle_new_miner,
        "0.0.0.0",
        INTERNAL_PROXY_PORT,
    )
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    logger.info(f"🔌 Proxy listening on {addrs}")

    # Dashboard
    app = create_dashboard_app(stats_manager)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        INTERNAL_DASHBOARD_PORT,
    )
    await site.start()
    logger.info(f"✅ Dashboard available at http://0.0.0.0:{INTERNAL_DASHBOARD_PORT}")

    await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down")
