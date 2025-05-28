import argparse
import os

from taohash.core.chain_data.pool_info import PoolInfo
from taohash.core.pool.config import PoolAPIConfig
from taohash.core.pool.pool import PoolIndex


class ProxyPoolAPIConfig(PoolAPIConfig):
    """Configuration for Proxy Pool API access"""

    def __init__(self, proxy_url: str, api_token: str):
        super().__init__()
        self.proxy_url = proxy_url
        self.api_token = api_token

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser") -> None:
        """Add Proxy API configuration arguments"""
        parser.add_argument(
            "--pool.proxy_url",
            type=str,
            required=False,
            default=os.getenv("PROXY_URL"),
            help="Proxy URL (e.g., http://proxy.example.com:8888) (env: PROXY_URL, required)",
        )
        parser.add_argument(
            "--pool.proxy_api_token",
            type=str,
            required=False,
            default=os.getenv("PROXY_API_TOKEN"),
            help="API token for proxy authentication (env: PROXY_API_TOKEN)",
        )

    @classmethod
    def from_args(cls, args) -> "ProxyPoolAPIConfig":
        proxy_url = args.pool.proxy_url
        if not proxy_url:
            # If not provided, construct from pool.ip as fallback
            if hasattr(args.pool, "ip") and args.pool.ip:
                proxy_url = f"http://{args.pool.ip}:8888"
            else:
                raise ValueError(
                    "Proxy URL must be provided via --pool.proxy_url or PROXY_URL env var, "
                    "or pool.ip must be set to auto-construct the URL"
                )

        api_token = args.pool.proxy_api_token
        if not api_token:
            raise ValueError(
                "Proxy API token must be provided via --pool.proxy_api_token or PROXY_API_TOKEN env var."
            )

        return cls(proxy_url=proxy_url, api_token=api_token)


class ProxyPoolConfig:
    """Configuration for Proxy Pool connection details"""

    DEFAULT_PORT = 8888
    DEFAULT_PASSWORD = "x"

    def __init__(
        self, ip: str, port: int, username: str, password: str = DEFAULT_PASSWORD
    ):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password

    def to_pool_info(self) -> PoolInfo:
        """Convert config to PoolInfo"""
        return PoolInfo(
            pool_index=int(PoolIndex.Proxy),
            ip=self.ip,
            port=self.port,
            username=self.username,
            password=self.password,
        )

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser") -> None:
        """Add Proxy pool connection arguments"""
        parser.add_argument(
            "--pool.ip",
            type=str,
            required=False,
            default=os.getenv("PROXY_IP"),
            help="Proxy IP address (env: PROXY_IP, required)",
        )
        parser.add_argument(
            "--pool.port",
            type=int,
            required=False,
            default=int(os.getenv("PROXY_PORT", str(cls.DEFAULT_PORT))),
            help=f"Proxy port (env: PROXY_PORT, default: {cls.DEFAULT_PORT})",
        )
        parser.add_argument(
            "--pool.username",
            type=str,
            required=False,
            default=os.getenv("PROXY_USERNAME"),
            help="Pool username (env: PROXY_USERNAME, required)",
        )
        parser.add_argument(
            "--pool.password",
            type=str,
            required=False,
            default=os.getenv("PROXY_PASSWORD", cls.DEFAULT_PASSWORD),
            help=f"Pool worker password (env: PROXY_PASSWORD, default: '{cls.DEFAULT_PASSWORD}')",
        )

    @classmethod
    def from_args(cls, args) -> "ProxyPoolConfig":
        ip = args.pool.ip
        if not ip:
            raise ValueError(
                "Proxy IP must be provided via --pool.ip or PROXY_IP env var."
            )

        username = args.pool.username
        if not username:
            raise ValueError(
                "Pool username must be provided via --pool.username or PROXY_USERNAME env var."
            )

        return cls(
            ip=ip, port=args.pool.port, username=username, password=args.pool.password
        )
