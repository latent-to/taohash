import abc


class PoolAPI(metaclass=abc.ABCMeta):
    """
    Abstract base class for pool APIs.
    """
    api_key: str

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @abc.abstractmethod
    def get_worker_data(self, worker_id: str, coin: str) -> dict:
        pass

    @abc.abstractmethod
    def get_fpps(self, coin: str) -> float:
        pass

    @staticmethod
    def _merge_worker_data(existing: dict | None, new: dict) -> dict:
        """
        Merge worker data, summing numeric metrics if existing data present.
        This is useful when miners use separate worker ids but the same hotkey.
        """
        if existing is None:
            return new.copy()

        for key, value in new.items():
            if isinstance(value, (int, float)):
                existing[key] = existing.get(key, 0) + value
        return existing
