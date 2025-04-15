import bittensor as bt
from typing import Optional

class WeightsSchedule:
    """
    Tracks block tempo to help synchronise evaluation windows.
    """
    
    def __init__(
        self,
        subtensor: "bt.subtensor",
        netuid: int,
        blocks_until_eval: Optional[int] = None,
        tempo: int = 360,
    ):
        """
        Args:
            subtensor: Bittensor subtensor instance
            netuid: Network UID
            blocks_until_eval: Number of blocks after which evaluation should begin (default: tempo - 20)
            tempo: Number of blocks in an epoch (default: 360)
        """
        self.subtensor = subtensor
        self.netuid = netuid
        self.tempo = tempo
        self.blocks_until_eval = blocks_until_eval or self.tempo - 20

    def blocks_until_evaluation(self) -> Optional[int]:
        """Get number of blocks until evaluation zone starts"""
        blocks = self.subtensor.subnet(self.netuid).blocks_since_last_step
        return self.blocks_until_eval - blocks
    
    def blocks_until_next_window(self) -> Optional[int]:
        """Get number of blocks until new tempo starts"""
        blocks = self.subtensor.subnet(self.netuid).blocks_since_last_step
        return self.tempo - blocks

    def get_status(self) -> str:
        """Get current status string for logging"""
        blocks = self.subtensor.subnet(self.netuid).blocks_since_last_step
            
        evaluation = blocks >= self.blocks_until_eval
        blocks_left = self.tempo - blocks if blocks else 0
        
        return (
            f"Blocks since Epoch: {blocks}/{self.tempo} | "
            f"Blocks remaining: {blocks_left} | "
            f"In evaluation zone: {evaluation}"
        )

    # For validators
    def should_set_weights(self) -> bool:
        """Check if validator should set weights"""
        blocks = self.subtensor.subnet(self.netuid).blocks_since_last_step
        return blocks >= self.blocks_until_eval
