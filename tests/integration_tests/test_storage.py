import time
from taohash.miner.storage import JsonStorage, RedisStorage
from bittensor.core.config import Config


example_pool_data = {
    "validator_hotkey_1": {
        "ip": "192.168.1.1",
        "port": 3333,
        "username": "user",
        "extra_data": {"full_username": "user.workerid"}
    }
}
example_block = int(time.time())


def test_storage_json():
    """Tests JSON storage."""
    config = Config()
    json_store = JsonStorage(config)
    json_store.save_pool_data(example_block, example_pool_data)

    loaded = json_store.get_pool_info(example_block)
    print("Loaded JSON data:", loaded)

    latest = json_store.get_latest_pool_info()
    print("Latest JSON:", latest)

    assert latest == example_pool_data


def test_storage_redis():
    """Tests Redis storage."""
    try:
        import redis
    except ImportError:
        print("Skipping Redis tests because redis is not installed.")
        exit()
    redis_config = Config()
    redis_config.redis_host = "localhost"
    redis_config.redis_port = 6379
    redis_config.redis_ttl = 15

    redis_store = RedisStorage(config=redis_config)
    redis_store.save_pool_data(example_block, example_pool_data)

    loaded_redis = redis_store.get_pool_info(example_block)
    assert loaded_redis == example_pool_data

    latest_redis = redis_store.get_latest_pool_info()
    print("Latest Redis:", latest_redis)

    assert latest_redis == example_pool_data


def test_generate_user_id_with_custom_network():
    """Tests user ID generation."""
    # Preps
    config = Config()
    config.wallet = Config()
    config.wallet.name = "test wallet"
    config.wallet.hotkey = "test hotkey"
    config.subtensor = Config()
    config.subtensor.network = "wss://subtensornodeurl.tao:9944"
    config.netuid = 332

    # call
    generate_user_id = JsonStorage.generate_user_id(config)

    # assert
    assert generate_user_id == "WSS___SUBTENSORNODEURL_TAO_9944_332_TEST_WALLET_TEST_HOTKEY"


def test_generate_user_id_with_empy_parts():
    """Tests user ID generation with empty parts in the config."""
    # prep
    config = Config()

    # call
    generate_user_id = JsonStorage.generate_user_id(config)

    # assert
    assert generate_user_id == "UNKNOWN_NONE_UNKNOWN_UNKNOWN"
