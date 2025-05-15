"""
Miner connection handler for Stratum protocol proxying.

Handles connections from mining clients, translates and forwards traffic to
upstream pools, and provides share tracking and difficulty management.
"""

import asyncio
import json
import re
from typing import Optional, Any

from .logger import get_logger
from .pool_session import PoolSession
from .stats import StatsManager

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

    def __init__(
        self,
        miner_reader: asyncio.StreamReader,
        miner_writer: asyncio.StreamWriter,
        pool_host: str,
        pool_port: int,
        pool_user: str,
        pool_pass: str,
        stats_manager: StatsManager,
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
        self.min_difficulty: Optional[int] = None
        # Register and track miner
        self.peer = miner_writer.get_extra_info("peername")
        self.miner_id = f"{self.peer[0]}:{self.peer[1]}" if self.peer else "unknown"
        self.stats = stats_manager.register_miner(self.peer)
        self.pool_session: Optional[PoolSession] = None
        self.pending_calls: dict[int, str] = {}  # Stratum ID -> method name

    async def run(self):
        """
        Main entry point to manage the miner's connection lifecycle.

        Connects to the pool, captures initial setup data, and starts
        the bidirectional proxying tasks. Handles disconnection cleanup.
        """
        # 1) Establish pool connection and complete handshake (subscribe + authorize)
        try:
            self.pool_session = await PoolSession.connect(
                self.pool_host, self.pool_port, self.pool_user, self.pool_pass
            )
        except Exception as e:
            logger.error(f"[{self.miner_id}] run: Pool connect/auth failed: {e}")
            self.close()
            return

        # Set initial difficulty
        self.stats.update_difficulty(1024)

        # Capture initial information from pool; without forwarding to miner yet
        extranonce1 = self.pool_session.extranonce1
        extranonce2_size = self.pool_session.extranonce2_size
        initial_difficulty = None
        initial_job = None

        async def drain_initial_messages():
            """
            Capture initial messages from pool to use during miner setup.
            """
            while True:
                line = await self.pool_session.reader.readline()
                if not line:
                    break
                try:
                    pool_message = json.loads(line.decode().strip())
                except json.JSONDecodeError:
                    continue

                method = pool_message.get("method")
                if method == "mining.set_difficulty":
                    nonlocal initial_difficulty
                    try:
                        initial_difficulty = float(pool_message["params"][0])
                    except (ValueError, TypeError, IndexError):
                        initial_difficulty = 1.0

                elif method == "mining.notify":
                    nonlocal initial_job
                    initial_job = pool_message
                    # Found a job, we can stop now
                    break

        await drain_initial_messages()

        # 2) Start bidirectional proxy loops
        miner_to_pool = asyncio.create_task(
            self._handle_from_miner(
                extranonce1, extranonce2_size, initial_difficulty, initial_job
            )
        )
        pool_to_miner = asyncio.create_task(self._handle_from_pool())

        _, pending = await asyncio.wait(
            [miner_to_pool, pool_to_miner], return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        self.close()

    async def _handle_from_miner(
        self,
        extranonce1: Optional[str] = None,
        extranonce2_size: Optional[int] = None,
        initial_difficulty: Optional[float] = None,
        initial_job: Optional[dict[str, Any]] = None,
    ):
        """
        Process messages from the miner and route them appropriately.

        Handles Stratum protocol messages from miners, either processing
        them locally (like subscribe/authorize) or forwarding to the pool.
        Manages miner setup and enforces difficulty constraints.

        Args:
            extranonce1: Pool-provided extranonce1 value
            extranonce2_size: Pool-provided extranonce2 size
            initial_difficulty: Initial difficulty from pool
            initial_job: First job notification from pool
        """
        try:
            while True:
                line = await self.miner_reader.readline()
                if not line:
                    # EOF: miner disconnected
                    break

                message_str = line.decode().strip()
                if not message_str:
                    continue

                try:
                    stratum_request = json.loads(message_str)
                except json.JSONDecodeError:
                    continue

                method = stratum_request.get("method")
                req_id = stratum_request.get("id")

                logger.debug(
                    f"[{self.miner_id}] _handle_from_miner: Received message method={method}, id={req_id}"
                )

                if method == "mining.subscribe":
                    await self._handle_subscribe(
                        stratum_request, req_id, extranonce1, extranonce2_size
                    )
                elif method == "mining.extranonce.subscribe":
                    await self._handle_extranonce_subscribe(stratum_request, req_id)
                elif method == "mining.configure":
                    await self._handle_configure(stratum_request, req_id)
                elif (
                    method == "mining.suggest_difficulty"
                    or method == "mining.suggest_target"
                ):
                    await self._handle_suggest_difficulty(stratum_request, req_id)
                elif method == "mining.authorize":
                    await self._handle_authorize(
                        stratum_request, req_id, initial_difficulty, initial_job
                    )
                elif method == "mining.submit":
                    await self._handle_submit(stratum_request, req_id)
                else:
                    # Any other message: forward as-is
                    logger.debug(
                        f"[{self.miner_id}] _handle_from_miner: Forwarding unknown method {method} to pool"
                    )
                    await self._send_to_pool(stratum_request)

        except ConnectionResetError:
            # Miner disconnected ungracefully; exit silently
            logger.debug(
                f"[{self.miner_id}] _handle_from_miner: Miner connection reset"
            )
            pass
        except asyncio.CancelledError:
            # Reraise CancelledError so run() can handle shutdown
            raise
        except Exception as e:
            logger.error(f"[{self.miner_id}] _handle_from_miner: Unexpected error: {e}")
        finally:
            return

    async def _handle_subscribe(
        self,
        stratum_request: dict[str, Any],
        req_id: Any,
        extranonce1: Optional[str],
        extranonce2_size: Optional[int],
    ):
        """
        Process mining.subscribe request from miners.

        Responds with extranonce info from the pool. Holds off on sending
        difficulty and job until after authorization is complete.

        Purpose: Initial handshake when miner registers with the pool and receives
        work subscription details including extranonce values.

        Args:
            stratum_request: The original subscribe message from miner
            req_id: Request ID from the message
            extranonce1: Pool-provided extranonce1 value
            extranonce2_size: Pool-provided extranonce2 size
        """
        logger.debug(
            f"[{self.miner_id}] _handle_subscribe: Processing mining.subscribe request id={req_id}"
        )

        # Use saved extranonce from pool connection if available
        if extranonce1 is not None and extranonce2_size is not None:
            resp = {
                "id": req_id,
                "result": [
                    [["mining.notify", "unused"], ["mining.set_difficulty", "unused"]],
                    extranonce1,
                    extranonce2_size,
                ],
                "error": None,
            }
            await self._send_to_miner(resp)
            logger.debug(
                f"[{self.miner_id}] _handle_subscribe: Sent extranonce1={extranonce1}, extranonce2_size={extranonce2_size}"
            )

            # We'll send difficulty AFTER authorization, not here
            # This ensures we respect the md parameter from the password
            # Don't send job yet either - wait for authorization
        else:
            # Forward to pool if we don't have cached values
            logger.debug(
                f"[{self.miner_id}] _handle_subscribe: No cached extranonce, forwarding to pool"
            )
            await self._send_to_pool(stratum_request)

    async def _handle_extranonce_subscribe(
        self, stratum_request: dict[str, Any], req_id: Any
    ):
        """
        Process mining.extranonce.subscribe requests with a success response.

        Purpose: Acknowledge miner extranonce subscription locally (no forwarding to pool).

        Args:
            stratum_request: The original message from miner
            req_id: Request ID from the message
        """
        logger.debug(
            f"[{self.miner_id}] _handle_extranonce_subscribe: Acknowledging extranonce subscription id={req_id}"
        )
        await self._send_to_miner({"id": req_id, "result": True, "error": None})

    async def _handle_configure(self, stratum_request: dict[str, Any], req_id: Any):
        """
        Process mining.configure requests from miners.

        Purpose: Negotiate version-rolling locally (proxy handles it without pool involvement).

        Args:
            stratum_request: The original message from miner
            req_id: Request ID from the message
        """
        logger.debug(
            f"[{self.miner_id}] _handle_configure: Processing mining.configure request id={req_id}"
        )
        await self._send_to_miner(
            {"id": req_id, "result": {"version-rolling": True}, "error": None}
        )

    async def _handle_suggest_difficulty(
        self, stratum_request: dict[str, Any], req_id: Any
    ):
        """
        Process difficulty suggestions from miners.

        Purpose: Enforce local min_difficulty if set and forward the effective suggestion to pool.

        Args:
            stratum_request: The original message from miner with difficulty suggestion
            req_id: Request ID from the message
        """
        difficulty_params = stratum_request.get("params", [])
        if difficulty_params and len(difficulty_params) > 0:
            try:
                suggested_diff = float(difficulty_params[0])
                if suggested_diff > 0:
                    # If minimum difficulty is set via password, enforce it
                    if self.min_difficulty is not None:
                        effective_diff = self.min_difficulty

                        # TODO: Alternative route: take the maximum value
                        # effective_diff = max(suggested_diff, self.min_difficulty)

                        self.stats.update_difficulty(effective_diff)
                        await self._send_to_miner(
                            {
                                "id": None,
                                "method": "mining.set_difficulty",
                                "params": [effective_diff],
                            }
                        )

                        # Forward the effective difficulty suggestion to the pool
                        stratum_request["params"][0] = effective_diff
                        await self._send_to_pool(stratum_request)
                        logger.debug(
                            f"[{self.miner_id}] _handle_suggest_difficulty: Miner suggested {suggested_diff}, enforced min={self.min_difficulty}, forwarded to pool"
                        )

                    else:
                        logger.debug(
                            f"[{self.miner_id}] _handle_suggest_difficulty: Miner suggested difficulty={suggested_diff}, forwarding to pool"
                        )
                        # We do NOT update stats here - wait for pool's mining.set_difficulty response
                        # The pool will respond with what difficulty it actually accepts

                        await self._send_to_pool(stratum_request)
            except (ValueError, TypeError):
                logger.warning(
                    f"[{self.miner_id}] _handle_suggest_difficulty: Invalid difficulty suggestion: {difficulty_params[0]}"
                )
                await self._send_to_pool(stratum_request)
        else:
            logger.debug(
                f"[{self.miner_id}] _handle_suggest_difficulty: Empty difficulty params, forwarding as-is"
            )
            await self._send_to_pool(stratum_request)

        # Ack the request
        await self._send_to_miner({"id": req_id, "result": True, "error": None})

    async def _handle_authorize(
        self,
        stratum_request: dict[str, Any],
        req_id: Any,
        initial_difficulty: Optional[float],
        initial_job: Optional[dict[str, Any]],
    ):
        """
        Process mining.authorize requests from miners.

        Purpose: Perform local authorization (proxy already authenticated upstream),
        extract and enforce min_difficulty, then send difficulty and initial job to miner.

        Args:
            stratum_request: The original authorize message from miner
            req_id: Request ID from the message
            initial_difficulty: Initial difficulty from pool
            initial_job: First job notification from pool
        """
        # params = [username, password]
        auth_params = stratum_request.get("params", [])
        username = auth_params[0] if len(auth_params) >= 1 else ""
        password = auth_params[1] if len(auth_params) >= 2 else ""

        logger.debug(
            f"[{self.miner_id}] _handle_authorize: Processing authorize for worker '{username}'"
        )

        _, min_diff = parse_min_difficulty(password)
        if min_diff is not None:
            self.min_difficulty = min_diff
            logger.info(
                f"[{self.miner_id}] _handle_authorize: Worker '{username}' set min_difficulty={min_diff} via password"
            )

        self.stats.worker_name = username
        await self._send_to_miner({"id": req_id, "result": True, "error": None})
        logger.debug(
            f"[{self.miner_id}] _handle_authorize: Sent authorization success response"
        )

        effective_diff = initial_difficulty if initial_difficulty is not None else 1024

        if self.min_difficulty is not None:
            pool_diff = effective_diff
            # TODO: Alternative route: take the maximum value
            # effective_diff = max(effective_diff, self.min_difficulty)
            effective_diff = self.min_difficulty
            if pool_diff != effective_diff:
                logger.info(
                    f"[{self.miner_id}] _handle_authorize: Applied min_difficulty={self.min_difficulty} over pool's {pool_diff}"
                )

        self.stats.update_difficulty(effective_diff)
        await self._send_to_miner(
            {"id": None, "method": "mining.set_difficulty", "params": [effective_diff]}
        )
        logger.info(
            f"[{self.miner_id}] _handle_authorize: Sent post-auth difficulty={effective_diff}"
        )

        if initial_job is not None:
            await self._send_to_miner(initial_job)
            logger.info(
                f"[{self.miner_id}] _handle_authorize: Sent initial job ID={initial_job.get('params', [None])[0] if initial_job.get('params') else None}"
            )

    async def _handle_submit(self, stratum_request: dict[str, Any], req_id: Any):
        """
        Process share submissions from miners.

        Purpose: Rewrite worker credentials to pool format (for TaoHash mining under HK derived username),
        forward the share to pool, and track submission for stats.

        Args:
            stratum_request: The share submission message
            req_id: Request ID from the message
        """
        self.pending_calls[req_id] = "submit"
        submit_params = stratum_request.get("params", [])

        job_id = submit_params[1] if len(submit_params) > 1 else "unknown"
        nonce = submit_params[2] if len(submit_params) > 2 else "unknown"
        logger.debug(
            f"[{self.miner_id}] _handle_submit: Processing share submission id={req_id}, job={job_id}, nonce={nonce}"
        )

        if submit_params:
            submit_params[0] = self.pool_user
            stratum_request["params"] = submit_params

        await self._send_to_pool(stratum_request)

    async def _handle_from_pool(self):
        """
        Process messages from the pool to forward to miners.

        Handles share submission responses, updates difficulty settings,
        and forwards mining jobs to the miner. Enforces minimum
        difficulty when appropriate.
        """
        try:
            while True:
                line = await self.pool_session.reader.readline()
                if not line:
                    # EOF: pool closed the connection
                    logger.debug(
                        f"[{self.miner_id}] _handle_from_pool: Pool connection closed"
                    )
                    break

                message_str = line.decode().strip()
                if not message_str:
                    continue

                try:
                    pool_response = json.loads(message_str)
                except json.JSONDecodeError:
                    continue

                msg_id = pool_response.get("id")
                method = pool_response.get("method")
                if method:
                    logger.debug(
                        f"[{self.miner_id}] _handle_from_pool: Received method={method}, id={msg_id}"
                    )
                else:
                    logger.debug(
                        f"[{self.miner_id}] _handle_from_pool: Received response id={msg_id}"
                    )

                # Match pool's mining.submit response to update share stats
                response_id = pool_response.get("id")
                if response_id in self.pending_calls:
                    method = self.pending_calls.pop(response_id)
                    if method == "submit":
                        submit_result = pool_response.get("result")
                        submit_error = pool_response.get("error")
                        share_accepted = submit_result is True and submit_error is None
                        self.stats.record_share(share_accepted, self.stats.difficulty)
                        logger.debug(
                            f"[{self.miner_id}] _handle_from_pool: Share response id={response_id}, accepted={share_accepted}, error={submit_error}"
                        )

                # Handle difficulty change from pool
                if pool_response.get("method") == "mining.set_difficulty":
                    difficulty_params = pool_response.get("params", [])
                    if difficulty_params:
                        try:
                            pool_diff = float(difficulty_params[0])
                        except (ValueError, TypeError, IndexError):
                            pool_diff = self.stats.difficulty
                            if pool_diff < 1.0:
                                pool_diff = 1.0

                        # Pool's requested difficulty
                        effective_diff = pool_diff

                        if self.min_difficulty is not None:
                            # TODO: Alternative route: take the maximum value
                            # effective_diff = max(effective_diff, self.min_difficulty)
                            effective_diff = self.min_difficulty
                        if effective_diff != self.stats.difficulty:
                            logger.info(
                                f"[{self.miner_id}] _handle_from_pool: Difficulty change from pool: {pool_diff}, "
                                + f"effective: {effective_diff} (was: {self.stats.difficulty})"
                            )

                            self.stats.update_difficulty(effective_diff)
                            pool_response["params"][0] = effective_diff
                        else:
                            logger.info(
                                f"[{self.miner_id}] _handle_from_pool: Pool attempted difficulty={pool_diff} but enforced={effective_diff}, not forwarded"
                            )
                            await self._send_to_pool(
                                {
                                    "id": None,
                                    "method": "mining.suggest_difficulty",
                                    "params": [effective_diff],
                                }
                            )
                            continue

                if pool_response.get("method") == "mining.notify":
                    job_id = (
                        pool_response.get("params", [None])[0]
                        if pool_response.get("params")
                        else None
                    )
                    logger.debug(
                        f"[{self.miner_id}] _handle_from_pool: Forwarding job notification, job_id={job_id}"
                    )

                # Forward everything else to miner
                await self._send_to_miner(pool_response)

        except ConnectionResetError:
            # Pool disconnected ungracefully; exit silently
            logger.debug(f"[{self.miner_id}] _handle_from_pool: Pool connection reset")
            pass
        except asyncio.CancelledError:
            # Reraise CancelledError so run() can handle shutdown
            raise
        except Exception as e:
            logger.error(f"[{self.miner_id}] _handle_from_pool: Unexpected error: {e}")
        finally:
            return

    async def _send_to_miner(self, stratum_message: dict[str, Any]):
        """
        Send a JSON message to the connected miner.

        Args:
            stratum_message: The message dictionary to encode and send
        """
        encoded_message = (json.dumps(stratum_message) + "\n").encode()
        self.miner_writer.write(encoded_message)
        await self.miner_writer.drain()

    async def _send_to_pool(self, stratum_message: dict[str, Any]):
        """
        Send a JSON message to the upstream pool.

        Args:
            stratum_message: The message dictionary to encode and send
        """
        encoded_message = (json.dumps(stratum_message) + "\n").encode()
        self.pool_session.writer.write(encoded_message)
        await self.pool_session.writer.drain()

    def close(self):
        """Close all connections and clean up resources."""
        try:
            self.miner_writer.close()
        except Exception as e:
            logger.debug(f"[{self.miner_id}] close (miner): Unexpected error: {e}")
            pass
        if self.pool_session:
            try:
                self.pool_session.writer.close()
            except Exception as e:
                logger.debug(f"[{self.miner_id}] close (pool): Unexpected error: {e}")
                pass
