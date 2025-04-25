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