from pathlib import Path

BLOCK_TIME = 12  # Seconds per block

MAIN_PATH = Path("~", ".bittensor", "taohash").expanduser()

VERSION_KEY = 27  # For validators
U16_MAX = 65535

OWNER_TAKE = 0.18
SPLIT_WITH_MINERS = 0.5