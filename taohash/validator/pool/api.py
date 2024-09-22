import abc


class PoolAPI(metaclass=abc.ABCMeta):
    api_key: str

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @abc.abstractmethod
    def get_hashrate_for_worker(worker_id: str) -> float:
        pass
