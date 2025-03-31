from ..config import PoolAPIConfig


class BraiinsPoolAPIConfig(PoolAPIConfig):
    api_key: str

    def __init__(self, api_key: str) -> None:
        super()
        self.api_key = api_key
