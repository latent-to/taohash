from pathlib import Path

BLOCK_TIME = 12  # Seconds per block

MAIN_PATH = Path("~", ".bittensor", "taohash").expanduser()

VERSION_KEY = 28  # For validators
U16_MAX = 65535

OWNER_TAKE = 0.18
SPLIT_WITH_MINERS = 0.5

FLOOR_PH = 30
FLOOR_PERCENTAGE = 0.5

CEILING_PH = 1000
CEILING_PERCENTAGE = 3.0
