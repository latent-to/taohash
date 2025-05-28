"""
Shared constants for the TaoHash proxy.
"""

# Used by controller to load new config in the running proxy
RELOAD_API_PORT = 5010  
RELOAD_API_HOST = "0.0.0.0"

# Used by miners to connect to the proxy
INTERNAL_PROXY_PORT = 3333  
DEFAULT_PROXY_PORT = 3333  

# Used by the controller to view the proxy stats
INTERNAL_DASHBOARD_PORT = 8100  
DEFAULT_DASHBOARD_PORT = 8100  

# Default path to the config file
CONFIG_PATH = "config/config.toml"  
