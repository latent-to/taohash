from typing import Any, List, Optional

from dataclasses import dataclass
from substrateinterface import SubstrateInterface


@dataclass
class Result:
    value: Optional[Any]


class Node:
    url: str
    substrate: SubstrateInterface

    def __init__(self, url: str) -> None:
        self.url = url
        self.substrate = SubstrateInterface(url=url)

    def query(self, module: str, method: str, params: List[Any]) -> Result:
        try:
            result = self.substrate.query(module, method, params).value
        except Exception:
            # reinitilize node
            self.substrate = Node(url=self.config.subtensor.chain_endpoint)
            result = self.substrate.query(module, method, params).value

        return Result(value=result)
