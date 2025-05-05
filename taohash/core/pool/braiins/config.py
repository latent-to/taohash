import argparse
import os

from taohash.core.chain_data.pool_info import PoolInfo
from taohash.core.pool.config import PoolAPIConfig
from taohash.core.pool.pool import PoolIndex


class BraiinsPoolAPIConfig(PoolAPIConfig):
    def __init__(
        self,
        api_key: str,
        use_primary_api: bool = True,
        primary_api_url: str = "http://localhost:8000",
        wallet=None,
    ) -> None:
        """Configuration for Braiins/Primary-pool HTTP layer.

        Args:
            api_key:  Braiins-cloud API key (ignored when *use_primary_api* is True)
            use_primary_api:  If True, proxy all requests through the local
                `primary_pool` FastAPI service instead of Braiins Cloud.
            primary_api_url:  Base-URL of the local primary-pool service.
            wallet:  bittensor.wallet instance whose hotkey will be used to sign
                authenticated requests against *primary_pool*.
        """
        super().__init__()
        self.api_key = api_key
        self.use_primary_api = use_primary_api
        self.primary_api_url = primary_api_url
        self.wallet = wallet  # Optional; only needed for PrimaryPoolAPI

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
        parser.add_argument(
            "--pool.use_primary_api",
            type=bool,
            required=False,
            default=os.getenv("BRAIINS_USE_PRIMARY_API", "true"),
            help="Use primary API for Braiins pool access (env: BRAIINS_USE_PRIMARY_API, default: true)",
        )
        parser.add_argument(
            "--pool.primary_api_url",
            type=str,
            required=False,
            default=os.getenv("BRAIINS_PRIMARY_API_URL", "http://localhost:8000"),
            help="Primary API URL for Braiins pool access (env: BRAIINS_PRIMARY_API_URL, default: http://localhost:8000)",
        )

    @classmethod
    def from_args(cls, args, wallet=None) -> "BraiinsPoolAPIConfig":
        """
        Create BraiinsPoolAPIConfig from command-line arguments.

        Returns:
            BraiinsPoolAPIConfig: Configured API client settings

        Raises:
            ValueError: When api_key is required but not provided

        Notes:
            - When `use_primary_api=True`: Uses the local taohash primary pool API,
              and api_key can be empty (will be provided "" as default)
            - When `use_primary_api=False`: Connects directly to Braiins cloud API,
              requires valid api_key to be provided
        """
        use_primary = args.pool.use_primary_api
        api_key = args.pool.api_key
        if not use_primary:
            if not api_key:
                raise ValueError(
                    "Braiins API key must be provided when not using primary API: via --pool.api_key or BRAIINS_API_KEY env var."
                )
        return cls(
            api_key=api_key or "",
            use_primary_api=use_primary,
            primary_api_url=args.pool.primary_api_url,
            wallet=wallet,
        )


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
            default=os.getenv("BRAIINS_POOL_PASSWORD", cls.DEFAULT_PASSWORD),
            help=f"Pool password (env: BRAIINS_POOL_PASSWORD, default: '{cls.DEFAULT_PASSWORD}')",
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
