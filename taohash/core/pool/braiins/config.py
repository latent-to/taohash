import argparse
import os

from taohash.core.chain_data.pool_info import PoolInfo
from taohash.core.pool.config import PoolAPIConfig
from taohash.core.pool.pool import PoolIndex


class BraiinsPoolAPIConfig(PoolAPIConfig):
    api_key: str

    def __init__(self, api_key: str) -> None:
        super().__init__()
        self.api_key = api_key

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser") -> None:
        """Add Braiins API configuration arguments"""
        parser.add_argument(
            "--pool.api_key",
            type=str,
            required=False,
            default=os.getenv("BRAIINS_API_KEY"),
            help="API key for Braiins pool access (env: BRAIINS_API_KEY, required)",
        )

    @classmethod
    def from_args(cls, args) -> "BraiinsPoolAPIConfig":
        api_key = args.pool.api_key
        if not api_key:
            raise ValueError(
                "Braiins API key must be provided via --pool.api_key or BRAIINS_API_KEY env var."
            )
        return cls(api_key=api_key)


class BraiinsPoolConfig:
    """Configuration for Braiins Pool connection details"""

    DEFAULT_DOMAIN = "stratum.braiins.com"
    DEFAULT_PORT = 3333
    DEFAULT_PASSWORD = "x"

    def __init__(self, domain: str, port: int, username: str, password: str) -> None:
        self.domain = domain
        self.port = port
        self.username = username
        self.password = password

    def to_pool_info(self) -> PoolInfo:
        """Convert config to PoolInfo"""
        return PoolInfo(
            pool_index=int(PoolIndex.Braiins),
            domain=self.domain,
            port=self.port,
            username=self.username,
            password=self.password,
        )

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser") -> None:
        """Add Braiins pool connection arguments"""
        parser.add_argument(
            "--pool.domain",
            type=str,
            required=False,
            default=os.getenv("BRAIINS_POOL_DOMAIN", cls.DEFAULT_DOMAIN),
            help=f"Pool domain (env: BRAIINS_POOL_DOMAIN, default: {cls.DEFAULT_DOMAIN})",
        )
        parser.add_argument(
            "--pool.port",
            type=int,
            required=False,
            default=int(os.getenv("BRAIINS_POOL_PORT", str(cls.DEFAULT_PORT))),
            help=f"Pool port (env: BRAIINS_POOL_PORT, default: {cls.DEFAULT_PORT})",
        )
        parser.add_argument(
            "--pool.username",
            type=str,
            required=False,
            default=os.getenv("BRAIINS_POOL_USERNAME"),
            help="Pool username (env: BRAIINS_POOL_USERNAME, required)",
        )
        parser.add_argument(
            "--pool.password",
            type=str,
            required=False,
            default=os.getenv("BRAIINS_WORKER_PASSWORD", cls.DEFAULT_PASSWORD),
            help=f"Pool worker password (env: BRAIINS_WORKER_PASSWORD, default: '{cls.DEFAULT_PASSWORD}')",
        )

    @classmethod
    def from_args(cls, args) -> "BraiinsPoolConfig":
        username = args.pool.username
        if not username:
            raise ValueError(
                "Braiins pool username must be provided via --pool.username or BRAIINS_POOL_USERNAME env var."
            )

        return cls(
            domain=args.pool.domain,
            port=args.pool.port,
            username=username,
            password=args.pool.password,
        )
