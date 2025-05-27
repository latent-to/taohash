#!/usr/bin/env python3
"""Generate secure API tokens for TaoHash Proxy API.

Usage:
    python generate_token.py        # Generate 1 token
    python generate_token.py 3      # Generate 3 tokens

Output tokens are added to API_TOKENS environment variable for API authentication.

Environment Setup:
    Add generated tokens to your .env file:
        API_TOKENS=token1,token2,token3
        
    Or export directly:
        export API_TOKENS="AbC123-_xYz789..."

API Usage:
    Use generated tokens to authenticate API requests:
        curl -H "Authorization: Bearer kX9mP2vN8qR5sT7wZ4eH6jL3nM9xB1cF5gK8pQ2vW" \\
             http://localhost:8888/api/pool/stats
"""

import secrets
import sys


def generate_token(length: int = 32) -> str:
    """Generate a secure random token for API authentication.

    Args:
        length: Number of random bytes (default: 32, produces ~43 char token)

    Returns:
        URL-safe base64-encoded token string

    The token is used in API_TOKENS environment variable and Authorization headers
    for accessing TaoHash Proxy API endpoints.
    """
    return secrets.token_urlsafe(length)


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    print("Generated API tokens:")
    print("=" * 50)

    tokens = []
    for i in range(count):
        token = generate_token()
        tokens.append(token)
        print(f"Token {i + 1}: {token}")

    print("\nAdd to your .env file:")
    print(f"API_TOKENS={','.join(tokens)}")
