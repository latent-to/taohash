import argparse
import os
import socket
import requests
import toml

import bittensor as bt
from bittensor.utils.btlogging import logging

from taohash.miner.proxy.base import BaseProxyManager

from .src.constants import (
    RELOAD_API_PORT,
    RELOAD_API_HOST,
    PROXY_PORT,
    PROXY_PORT_HIGH,
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
            default=int(os.getenv("PROXY_PORT", str(PROXY_PORT))),
            help="Port the proxy is running on",
        )
        proxy_group.add_argument(
            "--proxy_port_high",
            type=int,
            default=int(os.getenv("PROXY_PORT_HIGH", str(PROXY_PORT_HIGH))),
            help="Port the high diff proxy is running on",
        )
        proxy_group.add_argument(
            "--dashboard_port",
            type=int,
            default=int(os.getenv("DASHBOARD_PORT", str(DEFAULT_DASHBOARD_PORT))),
            help="Port for the proxy dashboard",
        )

    def __init__(self, config: "bt.Config"):
        super().__init__(config)
        self.base_path = os.path.expanduser(config.proxy_base_path)
        self.config_path = os.path.join(self.base_path, "config", "config.toml")
        self.proxy_port = config.proxy_port
        self.proxy_port_high = config.proxy_port_high
        self.dashboard_port = config.dashboard_port

        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        logging.info(f"Using taohash proxy configuration path: {self.config_path}")
        logging.info(f"Config directory: {os.path.dirname(self.config_path)}")
        logging.info(
            f"External ports - Normal: {self.proxy_port}, High Diff: {self.proxy_port_high}, Dashboard: {self.dashboard_port}"
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
                    return False, f"Normal proxy port {self.proxy_port} is not open"

            with socket.socket() as sock:
                sock.settimeout(1)
                if sock.connect_ex(("127.0.0.1", self.proxy_port_high)) != 0:
                    return (
                        False,
                        f"High diff proxy port {self.proxy_port_high} is not open",
                    )
        except Exception:
            pass

        return True, "All required files present and both proxy ports open"

    def update_config(self, pool_info: dict) -> bool:
        """
        Update proxy configuration with pool information.
        Writes to config.toml and triggers the proxy to reload.
        Uses high_diff_port field if available.
        """
        try:
            if self.verify_config_matches_pool(pool_info):
                logging.info("Proxy config already matches expected pool - no update needed")
                return True
                
            config = {"pools": {}}

            if pool_info:
                host, port = pool_info["pool_url"].split(":")
                username = pool_info["extra_data"]["full_username"]
                password = pool_info.get("password", "x")

                config["pools"]["normal"] = {
                    "host": host,
                    "port": int(port),
                    "user": username,
                    "pass": password,
                }

                logging.info(
                    f"🔄 Configured normal pool → {username}@{host}:{port} on proxy port {self.proxy_port}"
                )

                high_diff_port = pool_info.get("high_diff_port")
                if high_diff_port is not None:
                    config["pools"]["high_diff"] = {
                        "host": host,
                        "port": int(high_diff_port),
                        "user": username,
                        "pass": password,
                    }

                    logging.info(
                        f"🔄 Configured high_diff pool → {username}@{host}:{high_diff_port} (proxy listens on port {self.proxy_port_high})"
                    )
                else:
                    config["pools"]["high_diff"] = {
                        "host": host,
                        "port": int(port),
                        "user": username,
                        "pass": password,
                    }

                    logging.info(
                        f"🔄 High difficulty pool not specified, using same upstream port as normal pool (proxy listens on port {self.proxy_port_high})"
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

    def verify_config_matches_pool(self, pool_info: dict) -> bool:
        """
        Verify that the current TOML configuration matches the expected pool info.

        Args:
            pool_info: Pool information dictionary

        Returns:
            bool: True if config matches, False otherwise
        """
        try:
            if not os.path.exists(self.config_path):
                logging.debug("Config file does not exist")
                return False

            current_config = toml.load(self.config_path)

            if "pools" not in current_config:
                logging.debug("No pools section in config")
                return False

            if not pool_info:
                logging.debug("No pool info provided")
                return False

            expected_host = pool_info.get("domain") or pool_info.get("ip")
            expected_port = pool_info.get("port")
            expected_user = pool_info.get("extra_data", {}).get("full_username", "")

            # Normal pool
            normal_pool = current_config.get("pools", {}).get("normal", {})
            if (
                normal_pool.get("host") != expected_host
                or normal_pool.get("port") != expected_port
                or normal_pool.get("user") != expected_user
            ):
                logging.debug(
                    f"Normal pool mismatch - Expected: {expected_user}@{expected_host}:{expected_port}, "
                    f"Found: {normal_pool.get('user')}@{normal_pool.get('host')}:{normal_pool.get('port')}"
                )
                return False

            # High diff pool
            high_diff_pool = current_config.get("pools", {}).get("high_diff", {})
            expected_high_port = pool_info.get("high_diff_port", expected_port)
            if (
                high_diff_pool.get("host") != expected_host
                or high_diff_pool.get("port") != expected_high_port
                or high_diff_pool.get("user") != expected_user
            ):
                logging.debug(
                    f"High diff pool mismatch - Expected: {expected_user}@{expected_host}:{expected_high_port}, "
                    f"Found: {high_diff_pool.get('user')}@{high_diff_pool.get('host')}:{high_diff_pool.get('port')}"
                )
                return False

            logging.debug(
                "Config verification passed - TOML matches expected pool data"
            )
            return True

        except Exception as e:
            logging.debug(f"Error verifying config: {e}")
            return False
