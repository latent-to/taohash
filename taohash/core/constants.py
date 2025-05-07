from pathlib import Path

BLOCK_TIME = 12  # Seconds per block

MAIN_PATH = Path("~", ".bittensor", "taohash").expanduser()

VERSION_KEY = 26  # For validators
U16_MAX = 65535

BLACKLISTED_COLDKEYS = [
    "5CS96ckqKnd2snQ4rQKAvUpMh2pikRmCHb4H7TDzEt2AM9ZB"
]