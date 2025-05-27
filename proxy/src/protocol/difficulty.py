"""
Mining difficulty calculations and utilities.

This module provides functions for calculating share difficulty 
by recreating the block header and calculating the hash.
"""

import hashlib
import re
from typing import Optional, Any

from ..utils.logger import get_logger

logger = get_logger(__name__)


def calculate_share_difficulty(
    job: dict[str, Any],
    extranonce1: str,
    extranonce2: str,
    ntime: str,
    nonce: str,
    version: Optional[str] = None
) -> tuple[float, str]:
    """
    Calculate the actual difficulty of a submitted share.
    
    Uses the double SHA256 algorithm to compute the hash and derives
    the difficulty from the hash value.
    
    Args:
        job: Job data containing prevhash, coinb1, coinb2, merkle branches, etc.
        extranonce1: Extranonce1 assigned by pool
        extranonce2: Extranonce2 provided by miner
        ntime: Timestamp (hex)
        nonce: Nonce value (hex)
        version: Optional version string (hex)
        
    Returns:
        Tuple of (difficulty, block_hash_hex)
    """
    try:
        # Build coinbase transaction
        coinbase = job["coinb1"] + extranonce1 + extranonce2 + job["coinb2"]
        coinbase_hash = hashlib.sha256(hashlib.sha256(bytes.fromhex(coinbase)).digest()).digest()
        
        # Calculate merkle root
        merkle_root = coinbase_hash
        for branch in job["merkle_branches"]:
            branch_bytes = bytes.fromhex(branch)
            merkle_root = hashlib.sha256(hashlib.sha256(merkle_root + branch_bytes).digest()).digest()
        
        # Handle version - if miner provided version, XOR it with base version
        if version:
            # XOR to get the actual version used (for version rolling)
            version_int = int(job["version"], 16) ^ int(version, 16)
            version_hex = hex(version_int)[2:].zfill(8)
        else:
            version_hex = job["version"]
        
        # Build block header (80 bytes)
        # Special handling for prevhash: 8 x 4-byte chunks, each flipped to LE
        prevhash = job["prevhash"]
        prevhash_chunks = [prevhash[i:i+8] for i in range(0, 64, 8)]
        prevhash_bytes = b""
        for chunk in prevhash_chunks:
            prevhash_bytes += bytes.fromhex(chunk)[::-1]
        
        # Build the header
        header = b""
        header += bytes.fromhex(version_hex)[::-1]  # Version - 4 bytes LE
        header += prevhash_bytes  # Previous hash - 32 bytes (8x4 LE chunks)
        header += merkle_root  # Merkle root - 32 bytes
        header += bytes.fromhex(ntime)[::-1]  # Timestamp - 4 bytes LE
        header += bytes.fromhex(job["nbits"])[::-1]  # Bits - 4 bytes LE
        header += bytes.fromhex(nonce)[::-1]  # Nonce - 4 bytes LE
        
        # Calculate block hash (double SHA256)
        block_hash = hashlib.sha256(hashlib.sha256(header).digest()).digest()
        block_hash_hex = block_hash.hex()
        
        # Calculate difficulty from hash
        # Reverse the hash for difficulty calculation
        hash_bytes = [block_hash_hex[i:i+2] for i in range(0, 64, 2)]
        hash_reversed = "".join(hash_bytes[::-1])
        hash_int = int(hash_reversed, 16)
        
        if hash_int == 0:
            return 0.0, block_hash_hex
            
        # Standard difficulty 1 target
        max_target = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
        difficulty = max_target // hash_int
        
        return difficulty, block_hash_hex
        
    except Exception as e:
        logger.error(f"Error calculating share difficulty: {e}", exc_info=True)
        return 0.0, ""


def parse_min_difficulty(password: str) -> tuple[str, Optional[float]]:
    """
    Parse minimum difficulty from password field.
    
    Looks for the ';md=NUMBER' pattern in the password string.
    
    Args:
        password: Password string from mining.authorize
        
    Returns:
        Tuple of (clean_password, min_difficulty)
    """
    if not password:
        return password, None
        
    # find ';md=<digits>' at end or before another ';'
    min_diff_match = re.search(r";md=(\d+)(?:;|$)", password, flags=re.IGNORECASE)
    if not min_diff_match:
        return password, None
    
    min_diff_str = min_diff_match.group(1)
    try:
        min_diff_value = float(min_diff_str)
    except ValueError:
        # Invalid value, just remove it
        clean_password = re.sub(r";md=[^;]*(?:;|$)", "", password, flags=re.IGNORECASE)
        return clean_password, None
    
    # strip the ';md=N' part
    clean_password = re.sub(
        r";md=" + re.escape(min_diff_str) + r"(?:;|$)",
        "",
        password,
        flags=re.IGNORECASE,
    )
    return clean_password, min_diff_value


def difficulty_to_target(difficulty: float) -> int:
    """
    Convert difficulty to target value.
    
    Args:
        difficulty: Mining difficulty
        
    Returns:
        Target value as integer
    """
    if difficulty <= 0:
        return 0
        
    max_target = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
    return int(max_target / difficulty)


def target_to_difficulty(target: int) -> float:
    """
    Convert target value to difficulty.
    
    Args:
        target: Target value as integer
        
    Returns:
        Mining difficulty
    """
    if target <= 0:
        return 0.0
        
    max_target = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
    return max_target / target