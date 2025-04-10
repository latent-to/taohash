import json
from pathlib import Path
from typing import Dict, Optional
import bittensor as bt

class JsonStorage:
    DEFAULT_PATH = "~/.bittensor/data/pools"
    
    @classmethod
    def add_args(cls, parser):
        parser.add_argument(
            "--json_path",
            type=str,
            default=cls.DEFAULT_PATH,
            help="Path to save pool configuration JSON files"
        )

    def __init__(self, config):
        self.base_path = Path(config.json_path).expanduser()
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def save_pool_data(self, block_number: int, pool_mapping: Dict) -> None:
        """Save pool data for specific block."""
        pool_data_file = self.base_path / f"{block_number}-pools.json"
        with open(pool_data_file, "w") as f:
            json.dump(pool_mapping, f, indent=4)
    
    def get_pool_info(self, block_number: int) -> Optional[Dict]:
        """Get pool info for specific block."""
        pool_file = self.base_path / f"{block_number}-pools.json"
        if not pool_file.exists():
            return None
        with open(pool_file) as f:
            return json.load(f)
    
    def get_latest_pool_info(self) -> Optional[Dict]:
        """Get most recent pool info."""
        files = list(self.base_path.glob("*-pools.json"))
        if not files:
            return None
        latest_file = max(files, key=lambda f: int(f.stem.split("-")[0]))
        with open(latest_file) as f:
            return json.load(f)

class RedisStorage:
    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = 6379
    DEFAULT_TTL = 3600  # 1 hour in seconds
    
    @classmethod
    def add_args(cls, parser):
        redis_group = parser.add_argument_group('redis storage')
        redis_group.add_argument(
            "--redis_host",
            type=str,
            default=cls.DEFAULT_HOST,
            help="Redis host"
        )
        redis_group.add_argument(
            "--redis_port",
            type=int,
            default=cls.DEFAULT_PORT,
            help="Redis port"
        )
        redis_group.add_argument(
            "--redis_ttl",
            type=int,
            default=cls.DEFAULT_TTL,
            help="TTL for pool data in seconds"
        )

    def __init__(self, config):
        try:
            import redis
        except ImportError:
            raise ImportError("redis-py package required for Redis storage")
            
        self.redis = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            decode_responses=True
        )
        # Test connection
        self.redis.ping()
        self.ttl = config.redis_ttl
    
    def save_pool_data(self, block_number: int, pool_mapping: Dict) -> None:
        """Save pool data for specific block."""
        pool_data = json.dumps(pool_mapping)
        pipe = self.redis.pipeline()
        pipe.set(f"pool_info:{block_number}", pool_data, ex=self.ttl)
        pipe.set("latest_block", str(block_number))
        pipe.execute()
    
    def get_pool_info(self, block_number: int) -> Optional[Dict]:
        """Get pool info for specific block."""
        data = self.redis.get(f"pool_info:{block_number}")
        return json.loads(data) if data else None
    
    def get_latest_pool_info(self) -> Optional[Dict]:
        """Get most recent pool info."""
        latest_block = self.redis.get("latest_block")
        if not latest_block:
            return None
        data = self.redis.get(f"pool_info:{latest_block}")
        return json.loads(data) if data else None


STORAGE_CLASSES = {
    "json": JsonStorage,
    "redis": RedisStorage
}

def get_storage(storage_type: str, config) -> JsonStorage | RedisStorage:
    """Get storage instance based on type."""
    if storage_type not in STORAGE_CLASSES:
        raise ValueError(f"Unknown storage type: {storage_type}")
    
    storage_class = STORAGE_CLASSES[storage_type]
    try:
        return storage_class(config)
    except Exception as e:
        bt.logging.error(f"Failed to initialize {storage_type} storage: {e}")
        if storage_type == "redis":
            bt.logging.error("Please install redis-py package: pip install redis. After installing, make sure to start redis server.")
        exit(1)
