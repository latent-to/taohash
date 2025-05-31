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
        # TODO: Raise error if proxy_url is not set
        if not proxy_url:
            domain = None
            if hasattr(args.pool, "domain") and args.pool.domain:
                domain = args.pool.domain
            elif hasattr(args.pool, "ip") and args.pool.ip:
                domain = args.pool.ip

            if domain:
                proxy_url = f"http://{domain}:8888"
            else:
                raise ValueError(
                    "Proxy URL must be provided via --pool.proxy_url or PROXY_URL env var, "
                    "or pool.domain must be set to auto-construct the URL"
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
        self,
        domain: str,
        port: int,
        username: str,
        password: str = DEFAULT_PASSWORD,
        high_diff_port: int | None = None,
    ):
        self.domain = domain
        self.port = port
        self.username = username
        self.password = password
        self.high_diff_port = high_diff_port

    def to_pool_info(self) -> PoolInfo:
        """Convert config to PoolInfo"""
        return PoolInfo(
            pool_index=int(PoolIndex.Proxy),
            ip=None,
            domain=self.domain,
            port=self.port,
            username=self.username,
            password=self.password,
            high_diff_port=self.high_diff_port,
        )

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser") -> None:
        """Add Proxy pool connection arguments"""
        parser.add_argument(
            "--pool.domain",
            type=str,
            required=False,
            default=os.getenv("PROXY_DOMAIN", os.getenv("PROXY_IP")),
            help="Proxy domain or IP address (env: PROXY_DOMAIN or PROXY_IP)",
        )
        parser.add_argument(
            "--pool.ip",
            type=str,
            required=False,
            default=os.getenv("PROXY_IP"),
            help="[DEPRECATED] Use --pool.domain instead. Proxy IP address (env: PROXY_IP)",
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
        parser.add_argument(
            "--pool.high_diff_port",
            type=int,
            required=False,
            default=int(os.getenv("PROXY_HIGH_DIFF_PORT"))
            if os.getenv("PROXY_HIGH_DIFF_PORT")
            else None,
            help="Optional proxy port for high difficulty miners (env: PROXY_HIGH_DIFF_PORT)",
        )

    @classmethod
    def from_args(cls, args) -> "ProxyPoolConfig":
        domain = args.pool.domain
        if not domain and hasattr(args.pool, "ip") and args.pool.ip:
            domain = args.pool.ip

        if not domain:
            raise ValueError(
                "Proxy domain/IP must be provided via --pool.domain (or PROXY_DOMAIN/PROXY_IP env var)"
            )

        username = args.pool.username
        if not username:
            raise ValueError(
                "Pool username must be provided via --pool.username or PROXY_USERNAME env var."
            )

        high_diff_port = args.pool.high_diff_port
        if high_diff_port is not None:
            high_diff_port = int(high_diff_port)

        return cls(
            domain=domain,
            port=args.pool.port,
            username=username,
            password=args.pool.password,
            high_diff_port=high_diff_port,
        )
