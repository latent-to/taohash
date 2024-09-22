from typing import Any, List, Optional

from dataclasses import dataclass
from substrateinterface import SubstrateInterface


@dataclass
class Result:
    value: Optional[Any]


class Node:
    url: str
    _substrate: SubstrateInterface

    def __init__(self, url: str) -> None:
        self.url = url
        self._substrate = SubstrateInterface(url=url)

    def _check_connection(self): 
        try:
            _ = self._substrate.get_chain_finalised_head()
        except Exception:
             # reinitilize node
            self._substrate = SubstrateInterface(url=self.config.subtensor.chain_endpoint)

    def query(self, module: str, method: str, params: List[Any]) -> Result:
        self._check_connection()
    
        result = self._substrate.query(module, method, params).value

        return Result(value=result)
    
    def create_signed_extrinsic(self, *args, **kwargs) -> Any:
        self._check_connection()
        
        return self._substrate.create_signed_extrinsic(*args, **kwargs)
    
    def submit_extrinsic(self, *args, **kwargs) -> Any:
        self._check_connection()

        return self._substrate.submit_extrinsic(*args, **kwargs)
    
    def compose_call(self, *args, **kwargs) -> Any:
        self._check_connection()

        return self._substrate.compose_call(*args, **kwargs)
