# Bitcoin Mining Difficulty Calculation: A Complete Guide

This document explains how Bitcoin mining difficulty is calculated from Stratum protocol data. This involves understanding data formats, endianness, and cryptographic hashing.

## Table of Contents
1. [Overview](#overview)
2. [Stratum Protocol Data Format](#stratum-protocol-data-format)
3. [Data Conversion Requirements](#data-conversion-requirements)
4. [Building the Block Header](#building-the-block-header)
5. [Calculating the Hash](#calculating-the-hash)
6. [Calculating Difficulty](#calculating-difficulty)
7. [Complete Example](#complete-example)

## Overview

When a miner submits a share, we need to verify it actually did the work claimed. This involves:
1. Reconstructing the block header from Stratum data
2. Calculating the double SHA-256 hash
3. Converting the hash to a difficulty value
4. Comparing against the pool's required difficulty

## Stratum Protocol Data Format

Stratum sends data in specific formats that need careful handling:

### mining.subscribe Response
```json
{
  "id": 1,
  "result": [
    [
      ["mining.notify", "subscription_id"],
      ["mining.set_difficulty", "subscription_id"]
    ],
    "08000000",         // extranonce1 (8 hex chars)
    4                   // extranonce2_size
  ],
  "error": null
}
```

### mining.notify Message
```json
{
  "id": null,
  "method": "mining.notify",
  "params": [
    "job_id",           // Job identifier
    "prevhash",         // Previous block hash (64 hex chars)
    "coinb1",           // First part of coinbase transaction
    "coinb2",           // Second part of coinbase transaction
    ["merkle1", "..."], // Merkle branches
    "version",          // Block version (8 hex chars) - base version
    "nbits",            // Encoded difficulty target (8 hex chars)
    "ntime",            // Timestamp (8 hex chars)
    true                // Clean jobs flag
  ]
}
```

### mining.submit Message
```json
{
  "id": 4,
  "method": "mining.submit",
  "params": [
    "worker_name",      // Worker identifier
    "job_id",           // Job this submission is for
    "extranonce2",      // Miner's extranonce2 (miner chooses this)
    "ntime",            // Timestamp (possibly adjusted)
    "nonce",            // The golden nonce!
    "version_bits"      // Optional: version bits for version rolling
  ]
}
```

### Version Handling - Two Types!
1. **Base Version**: From mining.notify params[5]
2. **Version Bits**: From mining.submit params[5] (optional)
   - If provided, XOR with base version: `final_version = base_version ^ version_bits`
   - This is for version rolling (BIP320)

## Data Conversion Requirements

### Key Concepts:
1. **Hex Strings**: Stratum uses hex strings for all binary data
2. **Endianness**: Bitcoin uses a mix of big-endian and little-endian
3. **32-bit Words**: Many values are treated as 32-bit (4-byte) words

### Critical Conversions:

#### 1. Previous Hash (prevhash)
The prevhash is sent as a 64-character hex string but needs special handling:
- It represents 8 consecutive 32-bit words
- Each word must be converted to little-endian
- The overall order of words is preserved

```python
# Example: Convert prevhash for block header
prevhash = "00000000000000000002a6e8b55c7d9a5f8c4d2e1b9a7c5e3d2b1a0987654321"
prevhash_chunks = [prevhash[i:i+8] for i in range(0, 64, 8)]
prevhash_bytes = b""
for chunk in prevhash_chunks:
    prevhash_bytes += bytes.fromhex(chunk)[::-1]  # Reverse each 4-byte chunk
```

#### 2. Other Header Fields
These are simpler - just convert to little-endian:
- **version**: 4 bytes, little-endian
- **ntime**: 4 bytes, little-endian  
- **nbits**: 4 bytes, little-endian
- **nonce**: 4 bytes, little-endian

#### 3. Merkle Root
The merkle root stays in the byte order produced by the hashing algorithm.

## Building the Block Header

The Bitcoin block header is exactly 80 bytes:

| Field | Size | Description | Endianness |
|-------|------|-------------|------------|
| Version | 4 bytes | Block version | Little-endian |
| Previous Hash | 32 bytes | Hash of previous block | 8x4-byte LE chunks |
| Merkle Root | 32 bytes | Root of transaction tree | As calculated |
| Timestamp | 4 bytes | Unix timestamp | Little-endian |
| Bits | 4 bytes | Encoded difficulty | Little-endian |
| Nonce | 4 bytes | The number miners change | Little-endian |

### Step-by-Step Header Construction:

```python
# 1. Build coinbase transaction
coinbase = coinb1 + extranonce1 + extranonce2 + coinb2
coinbase_hash = sha256(sha256(bytes.fromhex(coinbase)))

# 2. Calculate merkle root - THIS IS CRITICAL!
# The merkle root calculation follows a specific algorithm:
# - Start with the coinbase transaction hash
# - For each branch hash provided by the pool:
#   - Concatenate current hash + branch hash (in that order!)
#   - Double SHA256 the concatenation
#   - This becomes the new current hash
# - The final hash is the merkle root

merkle_root = coinbase_hash  # Start with coinbase
for branch in merkle_branches:
    # IMPORTANT: Order matters! It's always (current_hash + branch)
    combined = merkle_root + bytes.fromhex(branch)
    merkle_root = sha256(sha256(combined))

# Visual example with 2 branches:
# Step 0: merkle_root = coinbase_hash
# Step 1: merkle_root = sha256(sha256(coinbase_hash + branch[0]))
# Step 2: merkle_root = sha256(sha256(step1_result + branch[1]))

# 3. Handle version rolling (if applicable)
if version_bits:
    version = hex(int(job_version, 16) ^ int(version_bits, 16))
else:
    version = job_version

# 4. Build the 80-byte header
header = b""
header += bytes.fromhex(version)[::-1]      # 4 bytes LE
header += prevhash_bytes                    # 32 bytes (special handling)
header += merkle_root                       # 32 bytes (as calculated above)
header += bytes.fromhex(ntime)[::-1]        # 4 bytes LE
header += bytes.fromhex(nbits)[::-1]        # 4 bytes LE
header += bytes.fromhex(nonce)[::-1]        # 4 bytes LE
```

### Merkle Root Calculation Explained

The merkle root represents all transactions in the block. The pool provides:
- **coinb1 & coinb2**: Parts of the coinbase transaction
- **merkle_branches**: Hashes representing other transactions

The algorithm builds a binary tree from bottom to top:
```
                    Merkle Root
                   /            \
            Hash(A+B)          Hash(C+D)
           /        \          /        \
     Coinbase      Tx1       Tx2       Tx3
```

But we only calculate the path from coinbase to root:
1. Hash the complete coinbase transaction
2. Combine with first branch (represents Tx1 subtree)
3. Combine result with second branch (represents Tx2+Tx3 subtree)
4. Continue until all branches are processed

## Calculating the Hash

Bitcoin uses double SHA-256:

```python
# First SHA-256
first_hash = hashlib.sha256(header).digest()

# Second SHA-256
block_hash = hashlib.sha256(first_hash).digest()

# Convert to hex for display
block_hash_hex = block_hash.hex()
```

## Calculating Difficulty

The difficulty calculation involves comparing the hash to a target:

```python
# 1. Reverse the hash bytes for numeric comparison
hash_bytes = [block_hash_hex[i:i+2] for i in range(0, 64, 2)]
hash_reversed = "".join(hash_bytes[::-1])
hash_int = int(hash_reversed, 16)

# 2. Compare to difficulty 1 target
max_target = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
difficulty = max_target // hash_int
```

### Why Reverse the Hash?
Bitcoin treats the hash as a 256-bit little-endian number for difficulty comparison. Since we calculated it as big-endian bytes, we need to reverse the byte order.

## Complete Example

Let's trace through a real submission showing the FULL flow:

```python
# Step 1: Miner connects and subscribes
subscribe_response = {
    "result": [
        [["mining.notify", "ae6812eb"], ["mining.set_difficulty", "b4b6693b"]],
        "08000000",  # <-- extranonce1
        4            # extranonce2 size
    ]
}
extranonce1 = subscribe_response["result"][1]  # Pool assigns this

# Step 2: Pool sends job via mining.notify
job = {
    "job_id": "0x123",
    "prevhash": "00000000000000000002a6e8b55c7d9a5f8c4d2e1b9a7c5e3d2b1a0987654321",
    "coinb1": "01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff20",
    "coinb2": "ffffffff0100f2052a010000001976a914abcdef1234567890abcdef1234567890abcdef1288ac00000000",
    "merkle_branches": ["abc123...", "def456..."],
    "version": "20000000",  # <-- Base version from job
    "nbits": "170cf4e3",
    "ntime": "6745a1b2"
}

# Step 3: Miner works and submits share
# Note: version_bits is optional (for version rolling)
extranonce2 = "00000000"  # Miner chooses this
ntime = "6745a1b2"         
nonce = "a294f8c2"         # Miner found this
version_bits = "00000004"  # Optional: miner's version bits

# Calculate difficulty
difficulty, block_hash = calculate_share_difficulty(
    job, 
    extranonce1,    # From subscribe
    extranonce2,    # Miner's choice
    ntime, 
    nonce,
    version_bits    # Optional - will be XORed with job version
)
```

## Critical Points Often Missed

1. **extranonce1 comes from mining.subscribe**: 
   - Pool assigns this to each miner connection
   - Essential for building the coinbase

2. **Two types of version**:
   - **Base version**: In mining.notify params[5]
   - **Version bits**: In mining.submit params[5] (optional)
   - If version bits provided: `final_version = base_version ^ version_bits`

3. **Complete flow**:
   ```
   1. mining.subscribe → get extranonce1
   2. mining.notify → get job with base version
   3. mining.submit → miner provides version_bits (optional)
   4. Calculate: use XORed version if version_bits provided
   ```

## Further Reading

- [Stratum Protocol Documentation](https://en.bitcoin.it/wiki/Stratum_mining_protocol)
- [BIP320: Version Rolling](https://github.com/bitcoin/bips/blob/master/bip-0320.mediawiki)