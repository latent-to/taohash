from typing import Any, Dict, List

from dataclasses import dataclass
import requests
import argparse

@dataclass
class PoolDetails:
    """
    lastStopCause 	string 	-
    extranonce2Size 	int 	-
    username 	string 	-
    numberOfWorkerConnections 	int 	-
    lastPoolMessage 	string 	-
    isActiveSince 	long 	-
    appendWorkerNames 	boolean 	-
    rejectedHashesPerSeconds 	long 	-
    isReadySince 	long 	-
    isReady 	boolean 	-
    isEnabled 	boolean 	-
    acceptedHashesPerSeconds 	long 	-
    weight 	int 	-
    rejectedDifficulty 	double 	-
    difficulty 	string 	-
    isActive 	boolean 	-
    isExtranonceSubscribeEnabled 	boolean 	-
    useWorkerPassword 	boolean 	-
    workerNamesSeparator 	string 	-
    workerExtranonce2Size 	int 	-
    host 	string 	-
    name 	string 	-
    extranonce1 	string 	-
    password 	string 	-
    priority 	int 	-
    lastStopDate 	long 	-
    isStable 	boolean 	-
    numberOfDisconnections 	int 	-
    acceptedDifficulty 	double 	-
    uptime 	long 	-
    """
    host: str
    name: str
    username: str
    password: str
    priority: int
    weight: int
    isEnabled: bool
  
    @staticmethod
    def from_json(json_data: Dict) -> 'PoolDetails':
        return PoolDetails(
            **json_data
        )
    
@dataclass
class PoolInfo:
    username: str
    appendWorkerNames: bool # TODO: No idea what this is for
    weight: int
    useWorkerPassword: bool 
    workerNamesSeparator: str # TODO: No idea what this is for
    isExtranonceSubscribeEnabled: bool # TODO: No idea what this is for
    host: str
    name: str
    priority: int
    password: str
    
    def to_json_data(self) -> Dict:
        return self.__dict__()
    
    def to_add_pool_data(self) -> Dict:
        add_pool = self.__dict__()
        FIELD_MAP = {
            "workerNameSeparator": "workerNamesSeparator",
            "enableExtranonceSubscribe": "isExtranonceSubscribeEnabled",
            "poolName": "name",
            "poolHost": "host",
            "password": "workerPassword",
        }

        for new, old in FIELD_MAP:
            if old is not None:
                add_pool[new] = add_pool[old]
                del add_pool[old]
        
        add_pool["enabled"] = True

        return add_pool

class ProxyAPI:
    url: str

    def __init__(self, url = "http://127.0.0.1:8888/proxy") -> None:
        self.url = url

    @staticmethod
    def add_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--"
        )

    def post(self, path: str, body: Dict) -> Any:
        response = requests.post(
            url=self.url + path,
            headers={
                "accept": "application/json"
            },
            data=body
        )

        return response
    
    def get(self, path: str, params: Dict) -> Any:
        response = requests.get(
            url=self.url + path,
            headers={
                "accept": "application/json"
            },
            params=params
        )

        return response

    def add_pool(self, pool_info: PoolInfo) -> None:
        path = "/pool/add"
        self.post(path, pool_info.to_add_pool_data())

    def enable_pool(self, pool: str) -> None:
        path = "/pool/enable"
        self.post(path, {
            "poolName": pool
        })

    def disable_pool(self, pool: str) -> None:
        path = "/pool/disable"
        self.post(path, {
            "poolName": pool
        })

    def update_pool(self, pool_info: PoolInfo) -> None:
        """
        Uses pool_info.name to specify the pool to update.
        """

        path = "/pool/update"
        self.post(path, pool_info.to_json())

    def get_pools(self) -> List[PoolDetails]:
        path = "/pool/list"
        pools = self.get(path, {}).json()

        return [PoolDetails.from_json(pool) for pool in pools]
    
    def remove_pool(self, pool: str) -> None:
        path = "/pool/remove"
        self.post(path, {
            "poolName": pool,
            "keepHistory": True # TODO: Not sure we need this
        })
