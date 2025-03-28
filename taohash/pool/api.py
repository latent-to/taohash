import abc

class PoolAPI(abc.ABC):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @abc.abstractmethod
    def get_shares_for_worker(self, worker_id: str, coin: str = "bitcoin") -> float:
        """
        Retrieve the number of shares for a given worker.
        """
        raise NotImplementedError("Subclasses must implement get_shares_for_worker")

    @abc.abstractmethod
    def get_fpps(self, coin: str = "bitcoin") -> float:
        """
        Retrieve the fee-per-share (FPPS) rate for the given coin.
        """
        raise NotImplementedError("Subclasses must implement get_fpps")
