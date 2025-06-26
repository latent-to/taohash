"""
Miner connection handler for Stratum protocol proxying.

Handles connections from mining clients, translates and forwards traffic to
upstream pools, and provides share tracking and difficulty management.
"""

import asyncio
import json
import re
import time
from typing import Optional, Any

from .logger import get_logger, log_stratum_message
from .pool_session import PoolSession
from .stats import StatsManager
from .miner_state import MinerStateMachine, MinerState

logger = get_logger(__name__)


def parse_min_difficulty(password: str) -> tuple[str, Optional[int]]:
    """
    Extract minimum difficulty parameter from password string.

    Looks for the ';md=NUMBER' pattern in the password string.
    Returns the password without the md parameter and the extracted value.

    Args:
        password: Miner password string potentially containing ';md=X'

    Returns:
        (clean_password, min_difficulty) - min_difficulty is None if not found
    """
    # find ';md=<digits>' at end or before another ';'
    min_diff_match = re.search(r";md=(\d+)(?:;|$)", password, flags=re.IGNORECASE)
    if not min_diff_match:
        return password, None

    min_diff_str = min_diff_match.group(1)
    try:
        min_diff_value = int(min_diff_str)
    except ValueError:
        logger.warning(
            f"parse_min_difficulty: Invalid min difficulty value '{min_diff_str}' in password '{password}'"
        )
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


class MinerSession:
    """
    Manages a single miner connection and proxies traffic to/from the pool.

    Handles the Stratum protocol, including:
    - Connection setup and authorization
    - Difficulty negotiation and enforcement
    - Job distribution
    - Share submission and tracking
    - Statistics gathering
    """

    def _get_worker_name(self) -> str:
        """Extract worker name from username."""
        if not self.stats.worker_name:
            return ""

        parts = self.stats.worker_name.split(".")
        if len(parts) > 1:
            return parts[-1]
        return self.stats.worker_name

    def __init__(
        self,
        miner_reader: asyncio.StreamReader,
        miner_writer: asyncio.StreamWriter,
        pool_host: str,
        pool_port: int,
        pool_user: str,
        pool_pass: str,
        stats_manager: StatsManager,
        pool_label: str,
    ):
        """
        Set up a new miner session with connection to pool.

        Args:
            miner_reader: Stream for reading from miner
            miner_writer: Stream for writing to miner
            pool_host: Upstream pool hostname/IP
            pool_port: Upstream pool port
            pool_user: Username for pool
            pool_pass: Password for pool
            stats_manager: Central stats tracking object
        """
        self.miner_reader = miner_reader
        self.miner_writer = miner_writer
        self.pool_host = pool_host
        self.pool_port = pool_port
        self.pool_user = pool_user
        self.pool_pass = pool_pass
        self.pool_label = pool_label
        self.min_difficulty: Optional[int] = None

        self.peer = miner_writer.get_extra_info("peername")
        self.miner_id = f"{self.peer[0]}:{self.peer[1]}" if self.peer else "unknown"
        self.stats = stats_manager.register_miner(self.peer)
        self.pool_session: Optional[PoolSession] = None
        self.pending_calls: dict[int, Any] = {}
        self.pending_configure = None

        self.state_machine = MinerStateMachine(self.miner_id)
        self.state_machine.on_state_change = self._on_state_change

        self.pool_init_data = {
            "extranonce1": None,
            "extranonce2_size": None,
            "subscription_ids": None,
            "initial_difficulty": None,
            "initial_job": None,
        }

        self._initial_pending_requests = []

        logger.info(f"[{self.miner_id}] Miner session initialized")

    async def _handle_initial_miner_requests(self):
        """
        Collect early miner requests before pool connection.

        Some miners send configure/subscribe immediately on connect.
        Stores these for processing after pool handshake.
        """
        logger.debug(f"[{self.miner_id}] Handling initial miner requests")

        pending_requests = []

        start_time = time.time()
        while time.time() - start_time < 1:
            try:
                line = await asyncio.wait_for(self.miner_reader.readline(), 0.1)
                if not line:
                    break

                message_str = line.decode().strip()
                if not message_str:
                    continue

                try:
                    request = json.loads(message_str)
                    method = request.get("method")
                    req_id = request.get("id")

                    logger.debug(
                        f"[{self.miner_id}] Initial request: method={method}, id={req_id}"
                    )

                    if method == "mining.configure":
                        self.pending_configure = request

                    elif method == "mining.suggest_difficulty":
                        await self._handle_suggest_difficulty(request, req_id)
                    else:
                        pending_requests.append(request)

                except json.JSONDecodeError:
                    logger.warning(f"[{self.miner_id}] Invalid JSON in initial request")

            except asyncio.TimeoutError:
                break

        self._initial_pending_requests = pending_requests

        logger.info(
            f"[{self.miner_id}] Collected {len(pending_requests)} pending requests"
        )

    async def run(self):
        """
        Main entry point to manage the miner's connection lifecycle.

        Connects to the pool, captures initial setup data, and starts
        the bidirectional proxying tasks. Handles disconnection cleanup.
        """
        try:
            await self._handle_initial_miner_requests()
            await self._connect_to_pool()

            miner_task = asyncio.create_task(self._handle_miner_messages())
            pool_task = asyncio.create_task(self._handle_pool_messages())

            _, pending = await asyncio.wait(
                [miner_task, pool_task], return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

        except Exception as e:
            logger.error(f"[{self.miner_id}] Session error: {e}")
            await self.state_machine.handle_error(e, "session_error")
        finally:
            await self._cleanup()

    async def _connect_to_pool(self):
        """
        Connect to upstream pool and retrieve mining parameters.

        Stores extranonce1, extranonce2_size from pool, processes any
        pre-auth messages (difficulty/job), then handles queued miner requests.
        """
        try:
            self.pool_session = await PoolSession.connect(
                self.pool_host, self.pool_port, self.pool_user, self.pool_pass,
                configure_request=self.pending_configure
            )

            # Store pool session data
            self.pool_init_data["extranonce1"] = self.pool_session.extranonce1
            self.pool_init_data["extranonce2_size"] = self.pool_session.extranonce2_size
            self.pool_init_data["subscription_ids"] = self.pool_session.subscription_ids

            await self._process_pool_init_messages()
            logger.info(f"[{self.miner_id}] Pool connection established")
            
            if self.pending_configure:
                logger.debug(f"[{self.miner_id}] Pending configure request: {self.pending_configure}")
                if self.pool_session:
                    if self.pool_session.configure_response is not None:
                        response = {
                            "id": self.pending_configure.get("id"),
                            "result": self.pool_session.configure_response,
                            "error": None
                        }
                        await self._send_to_miner(response)
                        logger.debug(f"[{self.miner_id}] Sent configure response to miner: {response}")
                    else:
                        params = self.pending_configure.get("params", [])
                        extensions = params[0] if len(params) > 0 else []
                        extension_params = params[1] if len(params) > 1 else {}
                        
                        result = {}
                        if "version-rolling" in extensions and "version-rolling.mask" in extension_params:
                            requested_mask = extension_params.get("version-rolling.mask", "00000000")
                            result["version-rolling"] = True
                            result["version-rolling.mask"] = requested_mask
                            logger.info(
                                f"[{self.miner_id}] Old validator detected - returning local version rolling support with mask: {requested_mask}"
                            )
                        
                        response = {
                            "id": self.pending_configure.get("id"),
                            "result": result,
                            "error": None
                        }
                        await self._send_to_miner(response)
                        logger.debug(f"[{self.miner_id}] Sent fallback configure response to miner: {response}")
                else:
                    logger.debug(f"[{self.miner_id}] No pool session available")
            else:
                logger.debug(f"[{self.miner_id}] No pending configure request")
            
            await self._process_pending_miner_requests()

        except Exception as e:
            logger.error(f"[{self.miner_id}] Pool connection failed: {e}")
            await self.state_machine.handle_error(e, "pool_connection")
            raise

    async def _process_pool_init_messages(self):
        """
        Extract initial mining params from pre-auth pool messages.

        Stores initial difficulty and first job notification for sending
        to miner after authorization completes.
        """
        if not self.pool_session or not self.pool_session.pre_auth_messages:
            return

        for msg in self.pool_session.pre_auth_messages:
            method = msg.get("method")

            if method == "mining.set_difficulty":
                try:
                    pool_diff = float(msg["params"][0])
                    self.pool_init_data["initial_difficulty"] = pool_diff
                    self.stats.pool_difficulty = pool_diff
                    logger.debug(
                        f"[{self.miner_id}] Got initial difficulty {pool_diff} from pool"
                    )
                except (ValueError, TypeError, IndexError):
                    pass

            elif method == "mining.notify":
                self.pool_init_data["initial_job"] = msg
                # Store job data
                await self._store_job_from_notify(msg)
                logger.debug(f"[{self.miner_id}] Got initial job from pool")

        self.pool_session.pre_auth_messages.clear()

    async def _process_pending_miner_requests(self):
        """
        Process miner requests collected during pool handshake.

        Handles subscribe/authorize that arrived before pool connection
        was ready with extranonce data.
        """
        logger.info(f"[{self.miner_id}] _process_pending_miner_requests called")
        logger.info(
            f"[{self.miner_id}] pool_init_data: extranonce1={self.pool_init_data['extranonce1']}, extranonce2_size={self.pool_init_data['extranonce2_size']}"
        )

        queued_messages = self._initial_pending_requests
        if queued_messages:
            logger.debug(
                f"[{self.miner_id}] Processing {len(queued_messages)} queued miner requests"
            )
            for msg in queued_messages:
                logger.debug(f"[{self.miner_id}] Queued message: {msg}")
        else:
            logger.warning(f"[{self.miner_id}] No queued messages found!")

        for message in queued_messages:
            try:
                logger.debug(
                    f"[{self.miner_id}] Processing queued message: {message.get('method')}"
                )
                await self._process_miner_message(message)
            except Exception as e:
                logger.error(
                    f"[{self.miner_id}] Error processing queued message: {e}",
                    exc_info=True,
                )

        self._initial_pending_requests = []

    async def _handle_miner_messages(self):
        """
        Main loop reading miner messages.

        Decodes Stratum messages and routes to _process_miner_message
        for state validation and handling.
        """
        try:
            while True:
                line = await self.miner_reader.readline()
                if not line:
                    break

                message_str = line.decode().strip()
                if not message_str:
                    continue

                try:
                    message = json.loads(message_str)
                    await self._process_miner_message(message)
                except json.JSONDecodeError as e:
                    logger.warning(f"[{self.miner_id}] Invalid JSON from miner: {e}")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[{self.miner_id}] Error handling miner messages: {e}")
            await self.state_machine.handle_error(e, "miner_handler")

    async def _handle_pool_messages(self):
        """
        Main loop reading pool messages.

        Decodes Stratum messages and routes to _process_pool_message
        for handling responses and notifications.
        """
        try:
            while True:
                if not self.pool_session:
                    break

                line = await self.pool_session.reader.readline()
                if not line:
                    break

                message_str = line.decode().strip()
                if not message_str:
                    continue

                try:
                    message = json.loads(message_str)
                    await self._process_pool_message(message)
                except json.JSONDecodeError as e:
                    logger.warning(f"[{self.miner_id}] Invalid JSON from pool: {e}")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[{self.miner_id}] Error handling pool messages: {e}")
            await self.state_machine.handle_error(e, "pool_handler")

    async def _process_miner_message(self, message: dict[str, Any]):
        """
        Route miner message to appropriate handler.

        Args:
            message: Stratum message dict with method/id/params

        Validates state before processing and queues/rejects invalid messages.
        """
        method = message.get("method")
        msg_id = message.get("id")
        handlers = {
            "mining.subscribe": self._handle_subscribe,
            "mining.authorize": self._handle_authorize,
            "mining.submit": self._handle_submit,
            "mining.extranonce.subscribe": self._handle_extranonce_subscribe,
            "mining.configure": self._handle_configure,
            "mining.suggest_difficulty": self._handle_suggest_difficulty,
            "mining.suggest_target": self._handle_suggest_difficulty,
        }

        if not method:
            # Response to a pool message - forwarding
            await self._send_to_pool(message)
            return

        log_stratum_message(logger, message, prefix=f"[{self.miner_id}] From miner")

        # Support for ASIC boost miners
        if method in ["mining.configure", "mining.extranonce.subscribe"]:
            handler = handlers.get(method)
            if handler:
                await handler(message, msg_id)
            return

        # Transition enforcement
        if not await self.state_machine.can_handle_message(method):
            if self.state_machine.state in {
                MinerState.CONNECTED,
                MinerState.SUBSCRIBING,
                MinerState.SUBSCRIBED,
            }:
                # Early in handshake - queue for later
                await self.state_machine.queue_message(message)
                logger.debug(
                    f"[{self.miner_id}] Queued {method} in state {self.state_machine.state.name}"
                )
            else:
                # Invalid message for state
                logger.warning(
                    f"[{self.miner_id}] Rejected {method} in state {self.state_machine.state.name}"
                )
                if msg_id is not None:
                    await self._send_error_to_miner(
                        msg_id, "Invalid message for current state"
                    )
            return

        handler = handlers.get(method)
        if handler:
            await handler(message, msg_id)
        else:
            # Unknown method - forward to pool
            logger.debug(
                f"[{self.miner_id}] Forwarding unknown method {method} to pool"
            )
            await self._send_to_pool(message)

    async def _process_pool_message(self, message: dict[str, Any]):
        """
        Route pool message to appropriate handler.

        Args:
            message: Stratum message from pool

        Handles responses to our requests (submits) and pool
        notifications (jobs, difficulty changes).
        """
        method = message.get("method")
        msg_id = message.get("id")

        log_stratum_message(logger, message, prefix=f"[{self.miner_id}] From pool")

        if msg_id is not None and msg_id in self.pending_calls:
            await self._handle_pool_response(message, msg_id)
            return

        # Handle pool notifications
        if method == "mining.notify":
            await self._handle_job_notify(message)
        elif method == "mining.set_difficulty":
            await self._handle_set_difficulty(message)
        elif method == "mining.set_extranonce":
            await self._handle_set_extranonce(message)
        else:
            if self.state_machine.state in {MinerState.AUTHORIZED, MinerState.ACTIVE}:
                await self._send_to_miner(message)
            else:
                await self.state_machine.queue_message(message)

    async def _handle_job_notify(self, message: dict[str, Any]):
        """Handle job notification from pool."""
        await self._store_job_from_notify(message)

        if self.state_machine.state == MinerState.AUTHORIZED:
            await self.state_machine.transition_to(MinerState.ACTIVE)

        if self.state_machine.state == MinerState.ACTIVE:
            await self._send_to_miner(message)

    async def _store_job_from_notify(self, message: dict[str, Any]):
        """Store job data from mining.notify."""
        params = message.get("params", [])
        if len(params) < 9:
            return

        job_id = params[0]
        logger.debug(f"[{self.miner_id}] Received job {job_id}")

    async def _handle_set_difficulty(self, message: dict[str, Any]):
        """Handle difficulty change from pool."""
        params = message.get("params", [])
        if not params:
            return

        try:
            pool_diff = float(params[0])
        except (ValueError, TypeError):
            return

        self.stats.pool_difficulty = pool_diff

        effective_diff = pool_diff
        if self.min_difficulty is not None:
            effective_diff = max(pool_diff, self.min_difficulty)
            if pool_diff > self.min_difficulty:
                logger.info(
                    f"[{self.miner_id}] Pool diff {pool_diff} > min diff {self.min_difficulty}, using pool diff"
                )
            else:
                logger.info(
                    f"[{self.miner_id}] Pool diff {pool_diff} < min diff {self.min_difficulty}, using min diff"
                )

        if effective_diff != self.stats.difficulty:
            logger.info(
                f"[{self.miner_id}] Difficulty: pool={pool_diff}, "
                f"effective={effective_diff}"
            )
            self.stats.update_difficulty(effective_diff)
            message["params"][0] = effective_diff

            if self.state_machine.state == MinerState.ACTIVE:
                await self._send_to_miner(message)

    async def _handle_set_extranonce(self, message: dict[str, Any]):
        """Handle extranonce change from pool."""
        params = message.get("params", [])
        if len(params) >= 2:
            new_extranonce1 = params[0]
            new_extranonce2_size = params[1]

            logger.info(
                f"[{self.miner_id}] Pool changed extranonce: "
                f"{new_extranonce1} (size {new_extranonce2_size})"
            )

            # Update pool session data
            if self.pool_session:
                self.pool_session.extranonce1 = new_extranonce1
                self.pool_session.extranonce2_size = new_extranonce2_size

            # Update init data for future reconnections
            self.pool_init_data["extranonce1"] = new_extranonce1
            self.pool_init_data["extranonce2_size"] = new_extranonce2_size

            if self.state_machine.state == MinerState.ACTIVE:
                await self._send_to_miner(message)

    async def _handle_pool_response(self, message: dict[str, Any], msg_id: int):
        """
        Process pool's response to our submit request.

        Args:
            message: Pool response with result/error
            msg_id: ID matching our original request

        Updates stats based on accept/reject status.
        """
        pending_data = self.pending_calls.pop(msg_id)

        if isinstance(pending_data, dict) and pending_data.get("method") == "submit":
            result = message.get("result")
            error = message.get("error")
            accepted = result is True and error is None

            self.stats.record_share(
                accepted=accepted,
                difficulty=pending_data.get("pool_difficulty", self.stats.difficulty),
                pool=self.pool_label or f"{self.pool_host}:{self.pool_port}",
                error=json.dumps(error) if error else None,
            )

            worker_name = self.stats.worker_name
            worker_prefix = f"{worker_name} - " if worker_name else ""

            if accepted:
                logger.info(f"[{self.miner_id}] {worker_prefix}Share accepted")
            else:
                reason = "unknown"
                if error:
                    if isinstance(error, list) and len(error) > 1:
                        reason = error[1]
                    else:
                        reason = str(error)
                logger.info(
                    f"[{self.miner_id}] {worker_prefix}Share rejected ({reason})"
                )

        await self._send_to_miner(message)

    async def _handle_subscribe(self, _: dict[str, Any], msg_id: Any):
        """
        Handle mining.subscribe - returns pool's extranonce data.

        Args:
            message: Subscribe request with optional miner version
            msg_id: Request ID for response

        Returns extranonce1 and extranonce2_size from pool.
        """
        logger.debug(f"[{self.miner_id}] Processing mining.subscribe")

        if not await self.state_machine.transition_to(MinerState.SUBSCRIBING):
            await self._send_error_to_miner(msg_id, "Invalid state for subscribe")
            return

        if (
            self.pool_init_data["extranonce1"] is not None
            and self.pool_init_data["extranonce2_size"] is not None
            and self.pool_init_data["subscription_ids"] is not None
        ):
            response = {
                "id": msg_id,
                "result": [
                    self.pool_init_data["subscription_ids"],
                    self.pool_init_data["extranonce1"],
                    self.pool_init_data["extranonce2_size"],
                ],
                "error": None,
            }
            await self._send_to_miner(response)

            await self.state_machine.transition_to(MinerState.SUBSCRIBED)
        else:
            logger.error(f"[{self.miner_id}] No pool extranonce data available")
            await self._send_error_to_miner(msg_id, "Pool connection not ready")
            await self.state_machine.handle_error(
                Exception("No extranonce"), "subscribe"
            )

    async def _handle_extranonce_subscribe(self, _: dict[str, Any], msg_id: Any):
        """
        Process mining.extranonce.subscribe requests with a success response.

        Purpose: Acknowledge miner extranonce subscription locally (no forwarding to pool).

        Args:
            message: The original message from miner
            msg_id: Request ID from the message
        """
        logger.debug(
            f"[{self.miner_id}] Acknowledging extranonce subscription id={msg_id}"
        )
        await self._send_to_miner({"id": msg_id, "result": True, "error": None})

    async def _handle_configure(self, message: dict[str, Any], msg_id: Any):
        """
        Handle mining.configure (version rolling) by forwarding to pool.

        Args:
            message: Configure request with extensions and parameters
            msg_id: Request ID for response

        Forwards configure requests to the pool for actual negotiation.
        Caches pool response for subsequent requests.
        """
        if self.pool_session:
            if self.pool_session.configure_response is not None:
                await self._send_to_miner({
                    "id": msg_id,
                    "result": self.pool_session.configure_response,
                    "error": None,
                })
                logger.debug(
                    f"[{self.miner_id}] Returned cached configure response to miner"
                )
            elif self.pool_session.configure_response is None:
                # Old vali (configure timed out) - provide local response
                params = message.get("params", [])
                extensions = params[0] if len(params) > 0 else []
                extension_params = params[1] if len(params) > 1 else {}
                
                result = {}
                if "version-rolling" in extensions and "version-rolling.mask" in extension_params:
                    requested_mask = extension_params.get("version-rolling.mask", "00000000")
                    result["version-rolling"] = True
                    result["version-rolling.mask"] = requested_mask
                    
                await self._send_to_miner({
                    "id": msg_id,
                    "result": result,
                    "error": None,
                })
                logger.debug(
                    f"[{self.miner_id}] Returned fallback configure response for old validator"
                )
            else:
                logger.debug(
                    f"[{self.miner_id}] Forwarding late mining.configure to pool"
                )
                await self._send_to_pool(message)
            return
        
        self.pending_configure = message
        logger.debug(
            f"[{self.miner_id}] Stored configure request until pool connection ready"
        )

    async def _handle_suggest_difficulty(self, message: dict[str, Any], msg_id: Any):
        """
        Process difficulty suggestions from miners.

        Purpose: Enforce local min_difficulty if set and forward the effective suggestion to pool.

        Args:
            message: The original message from miner with difficulty suggestion
            msg_id: Request ID from the message
        """
        await self._send_to_miner({"id": msg_id, "result": True, "error": None})

        params = message.get("params", [])
        if params and len(params) > 0:
            try:
                suggested = float(params[0])
                if suggested > 0 and self.min_difficulty is not None:
                    # Enforce minimum
                    effective = self.min_difficulty
                    self.stats.update_difficulty(effective)
                    await self._send_to_miner(
                        {
                            "id": None,
                            "method": "mining.set_difficulty",
                            "params": [effective],
                        }
                    )

                    message["params"][0] = effective
                    await self._send_to_pool(message)
                    logger.debug(
                        f"[{self.miner_id}] Miner suggested {suggested}, enforced min={self.min_difficulty}, forwarded to pool"
                    )
                else:
                    await self._send_to_pool(message)
            except (ValueError, TypeError):
                await self._send_to_pool(message)

    async def _handle_authorize(self, message: dict[str, Any], msg_id: Any):
        """
        Handle mining.authorize - authenticate worker.

        Args:
            message: Auth request with username/password params
            msg_id: Request ID for response

        Extracts min difficulty from password field (md=X format).
        Always returns success, then sends initial work.
        """
        params = message.get("params", [])
        username = params[0] if len(params) >= 1 else ""
        password = params[1] if len(params) >= 2 else ""

        logger.debug(f"[{self.miner_id}] Processing mining.authorize for {username}")

        if not await self.state_machine.transition_to(MinerState.AUTHORIZING):
            await self._send_error_to_miner(msg_id, "Invalid state for authorize")
            return

        _, min_diff = parse_min_difficulty(password)
        if min_diff is not None:
            self.min_difficulty = min_diff
            logger.info(
                f"[{self.miner_id}] Set min_difficulty={min_diff} from password"
            )

        self.stats.worker_name = username
        if self.pool_label:
            self.stats.pool_type = self.pool_label
        logger.info(f"[{self.miner_id}] Miner authorized with username: {username}")
        await self._send_to_miner({"id": msg_id, "result": True, "error": None})
        await self.state_machine.transition_to(MinerState.AUTHORIZED)
        await self._send_initial_work()

    async def _send_initial_work(self):
        """
        Send initial difficulty and job after successful authorization.

        Uses effective difficulty (min of pool/miner requirements) and
        forwards any cached initial job from pool.
        """
        pool_diff = self.pool_init_data["initial_difficulty"] or 1024
        effective_diff = pool_diff
        if self.min_difficulty is not None:
            effective_diff = max(pool_diff, self.min_difficulty)
            if pool_diff > self.min_difficulty:
                logger.info(
                    f"[{self.miner_id}] Initial: Pool diff {pool_diff} > min diff {self.min_difficulty}, using pool diff"
                )
            else:
                logger.info(
                    f"[{self.miner_id}] Initial: Pool diff {pool_diff} < min diff {self.min_difficulty}, using min diff"
                )

        self.stats.update_difficulty(effective_diff)
        await self._send_to_miner(
            {"id": None, "method": "mining.set_difficulty", "params": [effective_diff]}
        )

        if self.pool_init_data["initial_job"]:
            await self._send_to_miner(self.pool_init_data["initial_job"])
            await self.state_machine.transition_to(MinerState.ACTIVE)
        else:
            logger.debug(f"[{self.miner_id}] Waiting for initial job from pool")

    async def _handle_submit(self, message: dict[str, Any], msg_id: Any):
        """
        Handle share submission from miner.

        Args:
            message: Submit with [worker, job_id, extranonce2, ntime, nonce, version_bits]
            msg_id: Request ID for tracking response

        Forwards to pool and tracks submission for stats.
        """
        # Must be in Active state
        if self.state_machine.state != MinerState.ACTIVE:
            logger.warning(f"[{self.miner_id}] Submit rejected - not in ACTIVE state")
            await self._send_error_to_miner(msg_id, "Not ready for submissions")
            return

        params = message.get("params", [])
        worker_name = params[0] if len(params) > 0 else "unknown"
        job_id = params[1] if len(params) > 1 else "unknown"
        extranonce2 = params[2] if len(params) > 2 else ""
        ntime = params[3] if len(params) > 3 else ""
        nonce = params[4] if len(params) > 4 else ""
        version = params[5] if len(params) > 5 else None

        worker_name_display = self.stats.worker_name
        if worker_name_display:
            logger.info(
                f"[{self.miner_id}] {worker_name_display} - Share submission for job {job_id}"
            )
        else:
            logger.info(f"[{self.miner_id}] Share submission for job {job_id}")

        # Store submission details for when pool responds
        self.pending_calls[msg_id] = {
            "method": "submit",
            "worker": worker_name,
            "job_id": job_id,
            "extranonce2": extranonce2,
            "ntime": ntime,
            "nonce": nonce,
            "version": version,
            "pool_difficulty": self.stats.difficulty,
        }

        # Forward to pool with pool username
        message["params"][0] = self.pool_user
        await self._send_to_pool(message)

    async def _send_to_miner(self, stratum_message: dict[str, Any]):
        """
        Send a JSON message to the connected miner.

        Args:
            stratum_message: The message dictionary to encode and send
        """
        log_stratum_message(
            logger, stratum_message, prefix=f"[{self.miner_id}] Sent to miner"
        )
        encoded_message = (json.dumps(stratum_message) + "\n").encode()
        self.miner_writer.write(encoded_message)
        await self.miner_writer.drain()

    async def _send_to_pool(self, stratum_message: dict[str, Any]):
        """
        Send a JSON message to the upstream pool.
        """
        if not self.pool_session:
            logger.warning(f"[{self.miner_id}] Cannot send to pool - not connected")
            return

        log_stratum_message(
            logger, stratum_message, prefix=f"[{self.miner_id}] Sent to pool"
        )
        encoded_message = (json.dumps(stratum_message) + "\n").encode()
        self.pool_session.writer.write(encoded_message)
        await self.pool_session.writer.drain()

    async def _cleanup(self):
        """
        Clean up session resources on disconnect.

        Transitions state machine to DISCONNECTED and closes
        both miner and pool connections.
        """
        logger.info(f"[{self.miner_id}] Cleaning up session")

        await self.state_machine.start_disconnect()

        try:
            self.miner_writer.close()
            await self.miner_writer.wait_closed()
        except Exception:
            pass

        if self.pool_session:
            try:
                self.pool_session.writer.close()
                await self.pool_session.writer.wait_closed()
            except Exception:
                pass

        await self.state_machine.transition_to(MinerState.DISCONNECTED)

        summary = self.state_machine.get_state_summary()
        logger.info(f"[{self.miner_id}] Final state: {summary}")

    def _on_state_change(self, old_state: MinerState, new_state: MinerState):
        """Callback for state changes."""
        worker_name = (
            self.stats.worker_name if hasattr(self, "stats") and self.stats else ""
        )
        worker_prefix = f"{worker_name} - " if worker_name else ""

        logger.debug(
            f"[{self.miner_id}] {worker_prefix}State change: {old_state.name} -> {new_state.name}"
        )

        if new_state == MinerState.ACTIVE:
            logger.info(
                f"[{self.miner_id}] {worker_prefix}Miner is now actively mining"
            )
        elif new_state == MinerState.ERROR:
            logger.warning(
                f"[{self.miner_id}] {worker_prefix}Miner entered error state"
            )

    async def _send_error_to_miner(self, msg_id: Any, error_message: str):
        """Send error response to miner."""
        await self._send_to_miner(
            {"id": msg_id, "result": None, "error": [20, error_message, None]}
        )
