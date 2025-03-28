import abc

from .api import PoolAPI


class PoolBase(abc.ABC):
    """
    Abstract base class for mining pools.
    """

    def __init__(self, api_key: str, api: PoolAPI, ip: str, port: int) -> None:
        if not api_key:
            raise ValueError("API key must be provided")
        self.api_key = api_key
        self.api = api

    @staticmethod
    def _get_worker_id_for_hotkey(hotkey: str) -> str:
        """
        Maps a given hotkey to a worker identifier.
        """
        return hotkey

    @abc.abstractmethod
    def get_shares_for_hotkey(self, hotkey: str, coin: str = "bitcoin") -> float:
        """
        Retrieve the number of shares for a worker identified by the hotkey.
        """
        raise NotImplementedError("Subclasses must implement get_shares_for_hotkey")

    def get_fpps(self, coin: str = "bitcoin") -> float:
        """
        Retrieve the fee-per-share (FPPS) rate for the given coin.
        """
        try:
            return self.api.get_fpps(coin)
        except Exception as err:
            raise RuntimeError(f"Failed to retrieve FPPS for coin '{coin}'") from err

    @classmethod
    @abc.abstractmethod
    def create_api(cls, api_key: str) -> PoolAPI:
        """
        Factory method to instantiate a PoolAPI for this pool.
        """
        raise NotImplementedError("Subclasses must implement create_api")
