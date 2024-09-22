import typing
import bittensor as bt

class Dummy(bt.Synapse):
    """
    A simple dummy protocol that inherits from bt.Synapse.
    This protocol handles dummy request and response communication between
    the miner and the validator.

    Attributes:
    - dummy_input: An integer value representing the input request sent by the validator.
    - dummy_output: An optional integer value representing the response from the miner.
    """

    # Required request input, filled by the dendrite caller.
    dummy_input: int

    # Optional request output, filled by the axon responder.
    dummy_output: typing.Optional[int] = None