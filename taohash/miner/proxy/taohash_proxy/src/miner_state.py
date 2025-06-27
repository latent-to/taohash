"""
State machine for managing miner session lifecycle in Stratum protocol.

Enforces valid state transitions during the mining handshake sequence
and provides message queueing for out-of-order protocol messages.
"""

from enum import Enum, auto
from typing import Optional, Any, Callable
from dataclasses import dataclass, field
import asyncio
import time

from .logger import get_logger

logger = get_logger(__name__)


class MinerState(Enum):
    """
    States for miner session lifecycle.

    States:
        CONNECTED: TCP connection established, awaiting subscribe
        SUBSCRIBING: Processing mining.subscribe request
        SUBSCRIBED: Subscribe complete, awaiting authorize
        AUTHORIZING: Processing mining.authorize request
        AUTHORIZED: Authorized, awaiting initial work
        ACTIVE: Actively mining and submitting shares
        DISCONNECTING: Graceful shutdown in progress
        DISCONNECTED: Connection closed
        ERROR: Error state, invalid protocol flow
    """

    CONNECTED = auto()
    SUBSCRIBING = auto()
    SUBSCRIBED = auto()
    AUTHORIZING = auto()
    AUTHORIZED = auto()
    ACTIVE = auto()
    DISCONNECTING = auto()
    DISCONNECTED = auto()
    ERROR = auto()


@dataclass
class StateTransition:
    """
    Defines a valid state transition.

    Attributes:
        from_state: Source state
        to_state: Target state
        condition: Optional callable that must return True to allow transition
        on_transition: Optional callback executed after successful transition
    """

    from_state: MinerState
    to_state: MinerState
    condition: Optional[Callable[[], bool]] = None
    on_transition: Optional[Callable[[], None]] = None


@dataclass
class QueuedMessage:
    """
    Message queued for later processing.

    Attributes:
        message: Stratum protocol message dict
        timestamp: Unix timestamp when message was queued
    """

    message: dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class MinerStateMachine:
    """
    State machine for Stratum protocol session management.

    Enforces valid state transitions and queues messages that arrive
    out of order. Tracks state history and handles error conditions.

    Class Attributes:
        TRANSITIONS: Valid state transitions for the mining handshake flow
        ALLOWED_MESSAGES: Messages permitted in each state

    Instance Attributes:
        miner_id: Unique identifier for this miner session
        state: Current MinerState
        state_history: List of (state, timestamp) transitions
        message_queue: Messages queued per target state
        state_data: Arbitrary data storage for state context
        on_state_change: Optional callback for state transitions
    """

    TRANSITIONS: list[StateTransition] = [
        # Initial connection flow
        StateTransition(MinerState.CONNECTED, MinerState.SUBSCRIBING),
        StateTransition(MinerState.SUBSCRIBING, MinerState.SUBSCRIBED),
        StateTransition(MinerState.SUBSCRIBED, MinerState.AUTHORIZING),
        StateTransition(MinerState.AUTHORIZING, MinerState.AUTHORIZED),
        StateTransition(MinerState.AUTHORIZED, MinerState.ACTIVE),
        # Error transitions
        StateTransition(MinerState.SUBSCRIBING, MinerState.ERROR),
        StateTransition(MinerState.AUTHORIZING, MinerState.ERROR),
        # Disconnection from any state
        StateTransition(MinerState.CONNECTED, MinerState.DISCONNECTING),
        StateTransition(MinerState.SUBSCRIBING, MinerState.DISCONNECTING),
        StateTransition(MinerState.SUBSCRIBED, MinerState.DISCONNECTING),
        StateTransition(MinerState.AUTHORIZING, MinerState.DISCONNECTING),
        StateTransition(MinerState.AUTHORIZED, MinerState.DISCONNECTING),
        StateTransition(MinerState.ACTIVE, MinerState.DISCONNECTING),
        StateTransition(MinerState.ERROR, MinerState.DISCONNECTING),
        StateTransition(MinerState.DISCONNECTING, MinerState.DISCONNECTED),
    ]

    ALLOWED_MESSAGES: dict[MinerState, set[str]] = {
        MinerState.CONNECTED: {"mining.subscribe", "mining.configure"},
        MinerState.SUBSCRIBING: set(),
        MinerState.SUBSCRIBED: {"mining.authorize", "mining.configure"},
        MinerState.AUTHORIZING: set(),
        MinerState.AUTHORIZED: {
            "mining.submit",
            "mining.extranonce.subscribe",
            "mining.configure",
            "mining.suggest_difficulty",
            "mining.suggest_target",
        },
        MinerState.ACTIVE: {
            "mining.submit",
            "mining.extranonce.subscribe",
            "mining.configure",
            "mining.suggest_difficulty",
            "mining.suggest_target",
        },
        MinerState.DISCONNECTING: set(),
        MinerState.DISCONNECTED: set(),
        MinerState.ERROR: set(),
    }

    def __init__(self, miner_id: str):
        """
        Initialize state machine for a miner session.

        Args:
            miner_id: Unique identifier for the miner connection
        """
        self.miner_id = miner_id
        self.state = MinerState.CONNECTED
        self.state_history: list[tuple[MinerState, float]] = [(self.state, time.time())]
        self.message_queue: dict[MinerState, list[QueuedMessage]] = {
            state: [] for state in MinerState
        }
        self.state_data: dict[str, Any] = {}
        self._state_lock = asyncio.Lock()

        self.on_state_change: Optional[Callable[[MinerState, MinerState], None]] = None

        logger.info(f"[{self.miner_id}] State machine initialized in {self.state.name}")

    async def can_transition_to(self, new_state: MinerState) -> bool:
        """
        Check if transition to new state is valid.

        Args:
            new_state: Target state to transition to

        Returns:
            True if transition is allowed, False otherwise
        """
        for transition in self.TRANSITIONS:
            if transition.from_state == self.state and transition.to_state == new_state:
                if transition.condition:
                    return transition.condition()
                return True
        return False

    async def transition_to(self, new_state: MinerState) -> bool:
        """
        Transition to a new state with validation.

        Args:
            new_state: Target state

        Returns:
            True if transition succeeded, False if invalid

        Side effects:
            - Updates state history
            - Triggers on_state_change callback if set
            - Processes any queued messages for the new state
        """
        async with self._state_lock:
            if not await self.can_transition_to(new_state):
                logger.warning(
                    f"[{self.miner_id}] Invalid transition: {self.state.name} -> {new_state.name}"
                )
                return False

            old_state = self.state
            self.state = new_state
            self.state_history.append((new_state, time.time()))

            logger.info(
                f"[{self.miner_id}] State transition: {old_state.name} -> {new_state.name}"
            )

            for transition in self.TRANSITIONS:
                if (
                    transition.from_state == old_state
                    and transition.to_state == new_state
                ):
                    if transition.on_transition:
                        transition.on_transition()
                    break

            if self.on_state_change:
                self.on_state_change(old_state, new_state)

            await self._process_queued_messages(new_state)

            return True

    async def can_handle_message(self, method: str) -> bool:
        """
        Check if current state allows handling a Stratum method.

        Args:
            method: Stratum method name (e.g., 'mining.submit')

        Returns:
            True if message is allowed in current state
        """
        return method in self.ALLOWED_MESSAGES.get(self.state, set())

    async def queue_message(
        self, message: dict[str, Any], target_state: Optional[MinerState] = None
    ):
        """
        Queue a message for later processing.

        Args:
            message: The message to queue
            target_state: State in which to process this message (default: ACTIVE)
        """
        if target_state is None:
            target_state = MinerState.ACTIVE

        async with self._state_lock:
            self.message_queue[target_state].append(QueuedMessage(message))
            logger.debug(
                f"[{self.miner_id}] Queued message for {target_state.name}: "
                f"{message.get('method', 'response')}"
            )

    async def _process_queued_messages(self, state: MinerState) -> list[dict[str, Any]]:
        """
        Process and return queued messages for the current state.

        Returns list of messages that should be processed.
        """
        messages = self.message_queue[state]
        self.message_queue[state] = []

        if messages:
            logger.info(
                f"[{self.miner_id}] Processing {len(messages)} queued messages "
                f"for {state.name}"
            )

        return [qm.message for qm in messages]

    def get_state_duration(self, state: Optional[MinerState] = None) -> float:
        """
        Calculate total time spent in a specific state.

        Args:
            state: State to measure (defaults to current state)

        Returns:
            Total seconds spent in the specified state
        """
        if state is None:
            state = self.state

        total_time = 0.0
        current_state = None

        for i, (s, timestamp) in enumerate(self.state_history):
            if current_state == state:
                if i < len(self.state_history) - 1:
                    next_timestamp = self.state_history[i + 1][1]
                    total_time += next_timestamp - timestamp
                else:
                    total_time += time.time() - timestamp
            current_state = s

        return total_time

    def get_state_summary(self) -> dict[str, Any]:
        """
        Get comprehensive state machine status.

        Returns:
            Dict containing:
            - current_state: Current state name
            - state_duration: Seconds in current state
            - total_transitions: Number of state changes
            - queued_messages: Messages waiting per state
            - state_data: Arbitrary context data
        """
        return {
            "current_state": self.state.name,
            "state_duration": self.get_state_duration(),
            "total_transitions": len(self.state_history) - 1,
            "queued_messages": {
                state.name: len(messages)
                for state, messages in self.message_queue.items()
                if messages
            },
            "state_data": self.state_data,
        }

    async def handle_error(self, error: Exception, error_type: str = "unknown"):
        """
        Handle error by transitioning to ERROR state.

        Args:
            error: Exception that occurred
            error_type: Category of error for logging

        Stores error details in state_data['last_error'].
        """
        logger.error(
            f"[{self.miner_id}] Error in state {self.state.name}: {error_type} - {error}"
        )

        self.state_data["last_error"] = {
            "type": error_type,
            "message": str(error),
            "state": self.state.name,
            "timestamp": time.time(),
        }

        if self.state != MinerState.ERROR:
            await self.transition_to(MinerState.ERROR)

    async def start_disconnect(self):
        """
        Initiate graceful disconnection process.

        Transitions to DISCONNECTING state if not already disconnecting.
        """
        if self.state not in {MinerState.DISCONNECTING, MinerState.DISCONNECTED}:
            await self.transition_to(MinerState.DISCONNECTING)
