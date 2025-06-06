"""
Shared constants for the TaoHash proxy.
"""

import os

# Used by controller to load new config in the running proxy
RELOAD_API_PORT = 5010
RELOAD_API_HOST = "0.0.0.0"

# Used by miners to connect to the proxy
PROXY_PORT = 3331
PROXY_PORT_HIGH = 3332

# Used by the controller to view the proxy stats
INTERNAL_DASHBOARD_PORT = 8100
DEFAULT_DASHBOARD_PORT = 8100

# Default path to the config file
CONFIG_PATH = os.path.join("config", "config.toml")
