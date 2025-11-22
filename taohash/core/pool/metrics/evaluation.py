"""Evaluation metrics tracking for validator scoring."""

from dataclasses import dataclass
from typing import Optional, Any
from bittensor import logging
from taohash.core.constants import PAYOUT_FACTOR


@dataclass
class EvaluationMetrics:
    """
    Tracks evaluation metrics for a specific mining coin.

    Manages scores, payout factors, and timestamps for each evaluated coin
    by the validator.

    Attributes:
        coin: Coin identifier (e.g., 'btc', 'bch')
        scores: Raw scores per UID (before payout factor)
        payout_factor: Coin-specific payout percentage
        last_evaluation_timestamp: Unix timestamp of last successful evaluation
    """

    coin: str
    scores: list[float]
    payout_factor: float = PAYOUT_FACTOR
    last_evaluation_timestamp: Optional[int] = None

    def __init__(self, coin: str, num_hotkeys: int):
        """
        Initialize evaluation metrics for a coin.

        Args:
            coin: Coin identifier (e.g., 'btc', 'bch')
            num_hotkeys: Number of hotkeys/UIDs to track
        """
        self.coin = coin
        self.scores = [0.0] * num_hotkeys
        self.payout_factor = PAYOUT_FACTOR
        self.last_evaluation_timestamp = None

    def reset_scores(self, num_hotkeys: int) -> None:
        """
        Reset scores for new evaluation period.

        Args:
            num_hotkeys: Number of hotkeys/UIDs to track
        """
        self.scores = [0.0] * num_hotkeys

    def add_score(self, uid: int, value: float) -> None:
        """
        Add to a miner's score.

        Args:
            uid: Unique identifier for the miner
            value: Score value to add
        """
        if 0 <= uid < len(self.scores):
            self.scores[uid] += value
        else:
            logging.error(
                f"Invalid UID: {uid} for coin: {self.coin}. Out of sync metagraph."
            )

    def get_weighted_scores(self) -> list[float]:
        """
        Get scores with payout factor applied.

        Returns:
            list of scores multiplied by the payout factor
        """
        return [score * self.payout_factor for score in self.scores]

    def get_total_weighted_score(self) -> float:
        """
        Get the sum of all weighted scores.

        Returns:
            Total of all scores multiplied by payout factor
        """
        return sum(self.get_weighted_scores())

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize metrics for state saving.

        Returns:
            dictionary representation of the metrics
        """
        return {
            "scores": self.scores,
            "payout_factor": self.payout_factor,
            "last_evaluation_timestamp": self.last_evaluation_timestamp,
        }

    @classmethod
    def from_dict(
        cls, coin: str, data: dict[str, Any], num_hotkeys: int
    ) -> "EvaluationMetrics":
        """
        Deserialize metrics from saved state.

        Args:
            coin: Coin identifier
            data: dictionary containing saved state
            num_hotkeys: Number of hotkeys/UIDs

        Returns:
            EvaluationMetrics instance restored from saved data
        """
        metrics = cls(coin, num_hotkeys)
        metrics.scores = data.get("scores", [])
        metrics.payout_factor = data.get("payout_factor", PAYOUT_FACTOR)
        metrics.last_evaluation_timestamp = data.get("last_evaluation_timestamp")

        return metrics

    def __repr__(self) -> str:
        """String representation for debugging."""
        total_score = sum(self.scores)
        active_miners = sum(1 for s in self.scores if s > 0)
        return (
            f"EvaluationMetrics(coin={self.coin}, "
            f"active_miners={active_miners}, "
            f"total_score={total_score:.4f}, "
            f"payout_factor={self.payout_factor:.4f})"
        )
