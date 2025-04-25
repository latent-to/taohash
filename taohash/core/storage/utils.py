import pickle
import zlib
from pathlib import Path


def extract_block_number(file: Path) -> int:
    """Extracts the block number from a file name like 'pool-123.json'."""
    try:
        return int(file.stem.split("-")[1])
    except (IndexError, ValueError):
        return -1


def check_key(key):
    """Checks if the key is a string convertable."""
    try:
        return str(key)
    except TypeError:
        raise TypeError(f"Key '{key}' cannot be converted to string.")


def dumps(obj) -> bytes:
    """pickle + light zlib compression."""
    # You can choose not to use zlib - will be easier to use data in other services
    try:
        return zlib.compress(pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL), level=3)
    except Exception as e:
        raise Exception(f"Failed to pickle and compress object: {e}")


def loads(blob: bytes):
    """pickle + light zlib decompression."""
    try:
        return pickle.loads(zlib.decompress(blob))
    except Exception as e:
        raise Exception(f"Failed to decompress and unpickle object: {e}")
