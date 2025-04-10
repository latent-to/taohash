import argparse

from taohash.pool.config import PoolAPIConfig
from taohash.pool.pool import PoolIndex
from taohash.chain_data.chain_data import PoolInfo


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
            required=True,
            help="API key for Braiins pool access"
        )

    @classmethod
    def from_args(cls, args) -> "BraiinsPoolAPIConfig":
        return cls(api_key=args.pool.api_key)



class BraiinsPoolConfig:
    """Configuration for Braiins Pool connection details"""
    DEFAULT_DOMAIN = "stratum.braiins.com"
    DEFAULT_PORT = 3333

    def __init__(
        self,
        domain: str = DEFAULT_DOMAIN,
        port: int = DEFAULT_PORT,
        username: str = "",
        password: str = "x"
    ) -> None:
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
            default=cls.DEFAULT_DOMAIN,
            help=f"Pool domain (default: {cls.DEFAULT_DOMAIN})"
        )
        parser.add_argument(
            "--pool.port",
            type=int,
            default=cls.DEFAULT_PORT,
            help=f"Pool port (default: {cls.DEFAULT_PORT})"
        )
        parser.add_argument(
            "--pool.username",
            type=str,
            required=True,
            help="Pool username"
        )
        parser.add_argument(
            "--pool.password",
            type=str,
            default="x",
            help="Pool password (default: x)"
        )

    @classmethod
    def from_args(cls, args) -> "BraiinsPoolConfig":
        return cls(
            domain=args.pool.domain,
            port=args.pool.port,
            username=args.pool.username,
            password=args.pool.password
        )
