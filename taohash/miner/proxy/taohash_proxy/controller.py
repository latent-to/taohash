import argparse
import os
import socket
import requests
import toml
from typing import Any

import bittensor as bt
from bittensor.utils.btlogging import logging

from taohash.miner.proxy.base import BaseProxyManager

from .src.constants import (
    RELOAD_API_PORT,
    RELOAD_API_HOST,
    DEFAULT_PROXY_PORT,
    DEFAULT_DASHBOARD_PORT,
)

DEFAULT_PROXY_BASE_PATH = os.path.abspath(os.path.dirname(__file__))


class TaohashProxyManager(BaseProxyManager):
    """
    Manager for TaoHash mining proxy configuration.
    This manager assumes the TaoHash proxy is already installed and running.
    It only handles health checks and configuration updates.
    """

    @staticmethod
    def add_args(parser: "argparse.ArgumentParser") -> None:
        BaseProxyManager.add_args(parser)
        proxy_group = parser.add_argument_group("taohash_proxy")
        proxy_group.add_argument(
            "--proxy_base_path",
            type=str,
            default=os.getenv("PROXY_BASE_PATH", DEFAULT_PROXY_BASE_PATH),
            help="Path to the TaoHash proxy directory",
        )
        proxy_group.add_argument(
            "--proxy_port",
            type=int,
            default=int(os.getenv("PROXY_PORT", str(DEFAULT_PROXY_PORT))),
            help="Port the proxy is running on",
        )
        proxy_group.add_argument(
            "--dashboard_port",
            type=int,
            default=int(os.getenv("DASHBOARD_PORT", str(DEFAULT_DASHBOARD_PORT))),
            help="Port for the proxy dashboard",
        )

    def __init__(
        self,
        config: "bt.Config",
        proxy_base_path: str = DEFAULT_PROXY_BASE_PATH,
        proxy_port: int = DEFAULT_PROXY_PORT,
        dashboard_port: int = DEFAULT_DASHBOARD_PORT,
    ):
        super().__init__(config)
        self.base_path = os.path.expanduser(proxy_base_path)
        self.config_path = os.path.join(self.base_path, "config", "config.toml")
        self.proxy_port = proxy_port
        self.dashboard_port = dashboard_port

        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        logging.info(f"Using taohash proxy configuration path: {self.config_path}")
        logging.info(f"Config directory: {os.path.dirname(self.config_path)}")
        logging.info(
            f"External ports - Proxy: {self.proxy_port}, Dashboard: {self.dashboard_port}"
        )

        healthy, msg = self.check_health()
        if healthy:
            logging.info(f"Proxy manager health check passed: {msg}")
        else:
            logging.warning(f"Proxy manager health check failed: {msg}")
            logging.warning(
                "Mining will continue, but proxy configuration may not be updated correctly."
            )

    def check_health(self) -> tuple[bool, str]:
        required: list[str] = ["docker/docker-compose.yml", "docker/Dockerfile"]
        for file_name in required:
            file_path = os.path.join(self.base_path, file_name)
            if not os.path.exists(file_path):
                return False, f"Required Docker file not found: {file_path}"

        if not os.path.exists(self.config_path):
            return False, f"Config file not found at {self.config_path}"
        try:
            config: dict = toml.load(self.config_path)
            if "pools" not in config:
                return (
                    False,
                    "Invalid proxy configuration structure, 'pools' section not found",
                )

            if not config["pools"] or not any(
                all(k in pool for k in ["host", "port"])
                for pool in config["pools"].values()
            ):
                return (
                    False,
                    "Invalid proxy configuration structure, 'pools' section must contain pool configs with 'host' and 'port'",
                )
        except Exception as e:
            return False, f"Failed to read config file: {e}"

        try:
            with socket.socket() as sock:
                sock.settimeout(1)
                if sock.connect_ex(("127.0.0.1", self.proxy_port)) != 0:
                    return False, f"Proxy port {self.proxy_port} is not open"
        except Exception:
            pass

        return True, "All required files present and port open"

    def update_config(self, slot_data: Any) -> bool:
        """
        Called when a new slot's pool targets arrive.
        Writes them to config.toml and triggers the proxy to reload.
        Uses high_diff_port field if available.
        """
        try:
            config = {"pools": {}}

            if slot_data.pool_targets:
                target = slot_data.pool_targets[0]
                pool_info = target.pool_info

                host, port = pool_info["pool_url"].split(":")
                username = pool_info["extra_data"]["full_username"]
                password = pool_info.get("password", "x")

                config["pools"]["normal"] = {
                    "host": host,
                    "port": int(port),
                    "user": username,
                    "pass": password,
                    "proxy_port": self.proxy_port,
                }

                logging.info(
                    f"🔄 Configured normal pool → {username}@{host}:{port} on proxy port {self.proxy_port}"
                )

                high_diff_port = pool_info.get("high_diff_port")
                if high_diff_port is not None:
                    config["pools"]["high_diff"] = {
                        "host": host,
                        "port": int(port),
                        "user": username,
                        "pass": password,
                        "proxy_port": high_diff_port,
                    }

                    logging.info(
                        f"🔄 Configured high_diff pool → {username}@{host}:{port} on proxy port {high_diff_port}"
                    )
                else:
                    config["pools"]["high_diff"] = {
                        "host": host,
                        "port": int(port),
                        "user": username,
                        "pass": password,
                        "proxy_port": self.proxy_port,
                    }

                    logging.info(
                        "🔄 High difficulty pool not specified, using same port as normal pool"
                    )

            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w") as f:
                toml.dump(config, f)

            # Trigger reload
            try:
                reload_url = f"http://{RELOAD_API_HOST}:{RELOAD_API_PORT}/api/reload"
                requests.post(reload_url)
                logging.info(f"🔁 Reload triggered at {reload_url}")
            except Exception as e:
                logging.error(f"Failed to trigger proxy reload: {e}")
                return False

            return True

        except Exception as e:
            logging.error(f"Failed to update proxy config: {e}")
            return False
