import abc


class PoolAPI(metaclass=abc.ABCMeta):
    api_key: str

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @abc.abstractmethod
    def get_worker_data(self, worker_id: str, coin: str) -> dict:
        pass

    @abc.abstractmethod
    def get_fpps(self, coin: str) -> float:
        pass
