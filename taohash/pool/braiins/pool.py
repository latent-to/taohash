from taohash.pool.braiins.api import BraiinsPoolAPI
from taohash.pool import PoolIndex, PoolBase
import argparse




class BraiinsPool(PoolBase):
    api: BraiinsPoolAPI
    api_key: str
    index = PoolIndex.Braiins

    def __init__(self, api_key: str, api: BraiinsPoolAPI, *, ip: str, port: int) -> None:
        """Initialize BraiinsPool instance.

        Args:
            api_key (str): API key for Braiins pool
            api (BraiinsPoolAPI): Instance of BraiinsPoolAPI
            ip (str): IP address of the pool server
            port (int): Port number of the pool server
        """
        super().__init__(api_key, api, ip, port)
        self.ip = ip
        self.port = port

    def get_shares_for_hotkey(self, hotkey: str, coin: str) -> float:
        worker_id = self._get_worker_id_for_hotkey(hotkey)
        worker_shares = self.api.get_shares_for_worker(worker_id, coin)
        return worker_shares

    @classmethod
    def add_args(cls, parser: "argparse.ArgumentParser") -> None:
        """Add Braiins-specific arguments to the parser."""
        parser.add_argument(
            "--pool.user_id",
            type=str,
            required=True,
            help="User ID for Braiins pool"
        )
        parser.add_argument(
            "--pool.password",
            type=str,
            required=True,
            help="Password for Braiins pool"
        )

    @classmethod
    def create_api(cls, api_key: str, config: "argparse.Namespace") -> BraiinsPoolAPI:
        """Create a BraiinsPoolAPI instance with credentials from config."""
        return BraiinsPoolAPI(
            api_key=api_key,
            user_id=config.pool.user_id,
            password=config.pool.password
        )
