"""
Base metrics class for all pool implementations.
"""

from abc import ABC
from dataclasses import dataclass


@dataclass
class BaseMetrics(ABC):
    """
    Abstract base class for mining metrics.
    All pool-specific metrics should inherit from this class.
    """
    
    hotkey: str
    hash_rate_unit: str = "Gh/s"
    