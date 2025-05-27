"""
Main entry point for TaoHash Proxy when run as a Python module.

This file allows the package to be run directly with:
python -m src
"""

import asyncio
import sys
from .main import main, shutdown

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Clean shutdown on Ctrl+C
        try:
            asyncio.run(shutdown())
        except Exception:
            pass
    except Exception:
        sys.exit(1) 