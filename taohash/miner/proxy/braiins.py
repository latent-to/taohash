import os
import toml
import socket
import subprocess
from typing import Optional, Tuple, Any
import argparse
import bittensor as bt
from taohash.miner.proxy.base import BaseProxyManager


class BraiinsProxyManager(BaseProxyManager):
    """
    Manager for Braiins Farm Proxy configuration.
    
    This manager assumes the Braiins Farm Proxy is already installed and running.
    It only handles health checks and configuration updates.
    """
    
    @staticmethod
    def add_args(parser: "argparse.ArgumentParser") -> None:
        """
        Add proxy-related arguments to the parser
        
        Args:
            parser: The argument parser
        """
        BaseProxyManager.add_args(parser)
        
        proxy_group = parser.add_argument_group("braiins_proxy")
        proxy_group.add_argument(
            "--proxy_base_path",
            type=str,
            default="~/braiins-farm-proxy",
            help="Path to the Braiins Farm Proxy directory with docker-compose.yml",
        )
        proxy_group.add_argument(
            "--proxy_port",
            type=int,
            default=3333,
            help="Port the proxy is running on",
        )
    
    def __init__(
        self,
        config: "bt.Config",
        proxy_base_path: str = "~/braiins-farm-proxy",
        proxy_port: int = 3333,
    ):
        """
        Initialize the Braiins Proxy Manager
        
        Args:
            config: Bittensor config object
            proxy_base_path: Base path to the Braiins Farm Proxy installation
            proxy_port: Port the proxy is running on
        """
        super().__init__(config)

        self.base_path = os.path.expanduser(proxy_base_path)
        # Braiins Farm Proxy config path
        self.config_path = os.path.join(self.base_path, "config", "active_profile.toml")
        self.proxy_port = proxy_port
        
        # Ensure config directory exists
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        if not os.path.exists(self.config_path):
            bt.logging.info(f"Creating initial proxy configuration at {self.config_path}")
            self._create_initial_config()
            self._refresh_docker_config()

        health_status, message = self.check_health()
        if health_status:
            bt.logging.success(f"Proxy manager health check passed: {message}")
        else:
            bt.logging.warning(f"Proxy manager health check failed: {message}")
            bt.logging.warning(
                "Mining will continue, but proxy configuration may not be updated correctly."
            )
    
    def _create_initial_config(self) -> None:
        """Create initial proxy configuration file"""
        initial_config = {
            "description": "Initial taohash mining proxy configuration",
            
            "server": [{
                "name": "S1",
                "port": self.proxy_port
            }],
            
            "target": [],
            
            "routing": [{
                "name": "TaoHash",
                "from": ["S1"],
                "goal": []
            }]
        }
        
        with open(self.config_path, "w") as f:
            toml.dump(initial_config, f)
    
    def _refresh_docker_config(self) -> bool:
        """
        Refresh the Docker service to apply configuration changes
        
        Returns:
            bool: True if refresh was successful
        """
        try:
            bt.logging.info("Refreshing Braiins Farm Proxy configuration...")
            
            result = subprocess.run(
                [
                    "docker", "compose", 
                    "--project-directory", self.base_path, 
                    "up", "-d", "farm-proxy-configurator"
                ],
                check=True,
                capture_output=True,
                text=True
            )
            
            bt.logging.success("Successfully refreshed proxy configuration")
            return True
                
        except subprocess.CalledProcessError as e:
            bt.logging.error(f"Failed to refresh proxy configuration: {e.stderr}")
            return False
        except Exception as e:
            bt.logging.error(f"Error refreshing proxy configuration: {str(e)}")
            return False
    
    def check_health(self) -> Tuple[bool, Optional[str]]:
        """
        This performs two checks:
        1. Verifies the config file exists and is readable
        2. Checks if the proxy port is open and listening
        
        Returns:
            Tuple[bool, Optional[str]]:
                - Health status (True if healthy)
                - Status message or error description
        """
        if not os.path.exists(self.config_path):
            return False, f"Config file not found at {self.config_path}"
        
        try:
            with open(self.config_path, "r") as f:
                config = toml.load(f)
            
            if not config.get("server") or not config.get("routing"):
                return False, "Invalid proxy configuration structure"
        except Exception as e:
            return False, f"Failed to read config file: {str(e)}"
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('127.0.0.1', self.proxy_port))
                if result != 0:
                    return False, f"Proxy port {self.proxy_port} is not open"
        except Exception as e:
            bt.logging.warning(f"Could not check proxy port: {str(e)}")
            pass
            
        return True, f"Proxy configuration healthy at {self.config_path}"
    
    def update_config(self, slot_data: Any) -> bool:
        """
        Update the proxy configuration for a new mining slot
        
        Args:
            slot_data: MiningSlot object containing information about the new slot
            
        Returns:
            bool: True if update was successful
        """
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    config = toml.load(f)
            else:
                self._create_initial_config()
                with open(self.config_path, "r") as f:
                    config = toml.load(f)
            
            pool_url = slot_data.pool_info["pool_url"]
            username = slot_data.pool_info["extra_data"]["full_username"]
            validator_id = slot_data.validator_hotkey[:8]
            
            config["description"] = f"Mining to {validator_id} for blocks {slot_data.start_block}-{slot_data.end_block}"
            
            # Set up target with proper fields
            target_name = f"Pool-{validator_id}"
            config["target"] = [{
                "name": target_name,
                "url": f"stratum+tcp://{pool_url}",
                "user_identity": username
            }]
            
            # Set up proper routing structure with goal and level
            goal_name = f"Mine-{username}"
            config["routing"][0]["goal"] = [{
                "name": goal_name,
                "level": [{
                    "targets": [target_name]
                }]
            }]
            
            with open(self.config_path, "w") as f:
                toml.dump(config, f)
                
            bt.logging.success(
                f"Updated proxy configuration for Validator {validator_id}: "
                f"{username} → {pool_url}"
            )
            
            # Refresh Docker to apply changes to the proxy
            if not self._refresh_docker_config():
                bt.logging.warning("Failed to refresh Docker configuration - changes may not be applied")
                return False
            
            return True
            
        except Exception as e:
            bt.logging.error(f"Failed to update proxy configuration: {e}")
            return False 
