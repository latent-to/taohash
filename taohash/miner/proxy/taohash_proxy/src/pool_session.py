"""
Pool connection management module.

This module handles the connection to the upstream mining pool using the Stratum
protocol. It manages the initial handshake process, including subscription and
authorization, and provides the connection interface used by the miner sessions.
"""

import asyncio
import json
from typing import Optional, Any

from .logger import get_logger, log_stratum_message

logger = get_logger(__name__)


class PoolSession:
    """
    Manages a connection to an upstream mining pool.

    This class encapsulates the connection to a mining pool, handles the initial
    protocol handshake (subscribe and authorize), and maintains the pool connection
    state including the extranonce values needed for mining.

    Attributes:
        reader (StreamReader): Async stream reader for pool communication
        writer (StreamWriter): Async stream writer for pool communication
        _msg_id (int): Counter for generating unique message IDs
        extranonce1 (str): Extranonce1 value assigned by the pool
        extranonce2_size (int): Size of extranonce2 required by the pool
        pre_auth_messages (list[dict]): Messages received during the authorization phase
    """

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Initialize a new pool session.

        Args:
            reader (StreamReader): Async stream reader for pool communication
            writer (StreamWriter): Async stream writer for pool communication
        """
        self.reader = reader
        self.writer = writer
        self._msg_id = 1
        self.extranonce1: Optional[str] = None
        self.extranonce2_size: Optional[int] = None
        self.subscription_ids: Optional[list] = None
        self.pre_auth_messages: list[dict[str, Any]] = []

    def next_id(self) -> int:
        """
        Generate a unique message ID for Stratum protocol messages.

        Returns:
            int: Unique message ID
        """
        current_id = self._msg_id
        self._msg_id += 1
        return current_id

    @classmethod
    async def connect(
        cls, host: str, port: int, user: str, password: str
    ) -> "PoolSession":
        """
        Create a pool connection and perform the Stratum protocol handshake.

        This method connects to the pool, performs the subscribe and
        authorize operations, and returns a fully initialized PoolSession.

        Args:
            host (str): Pool hostname or IP address
            port (int): Pool port number
            user (str): Username for pool authentication
            password (str): Password for pool authentication

        Returns:
            PoolSession: Initialized pool session object

        Raises:
            RuntimeError: If pool authentication fails
        """
        logger.info(f"Connecting to pool at {host}:{port} with user {user}")
        try:
            pool_reader, pool_writer = await asyncio.open_connection(host, port)
            pool_session = cls(pool_reader, pool_writer)

            # 1) Subscribe
            subscription_id = pool_session.next_id()
            subscription_request = {
                "id": subscription_id,
                "method": "mining.subscribe",
                "params": ["async_proxy", None],
            }
            pool_writer.write((json.dumps(subscription_request) + "\n").encode())
            await pool_writer.drain()
            log_stratum_message(
                logger,
                subscription_request,
                f"Sent subscription request with id {subscription_id}",
            )

            subscription_response_raw = await pool_reader.readline()
            subscription_response = json.loads(subscription_response_raw.decode())
            log_stratum_message(
                logger,
                subscription_response,
                f"Received subscription response: {subscription_response}",
            )

            # Parse and store subscription_ids, extranonce1, extranonce2_size
            subscription_result = subscription_response.get("result", [])
            pool_session.subscription_ids = subscription_result[0]
            pool_session.extranonce1 = subscription_result[1]
            pool_session.extranonce2_size = subscription_result[2]
            logger.info(
                f"Subscription successful, extranonce1: {pool_session.extranonce1}, extranonce2_size: {pool_session.extranonce2_size}"
            )

            # 2) Authorize
            authorization_id = pool_session.next_id()
            authorization_request = {
                "id": authorization_id,
                "method": "mining.authorize",
                "params": [user, password],
            }
            pool_writer.write((json.dumps(authorization_request) + "\n").encode())
            await pool_writer.drain()
            log_stratum_message(
                logger,
                authorization_request,
                f"Sent authorization request with id {authorization_id}",
            )

            authorization_response = None
            max_pre_auth_messages = 10
            message_count = 0

            while message_count < max_pre_auth_messages:
                try:
                    authorization_response_raw = await asyncio.wait_for(
                        pool_reader.readline(), timeout=30.0
                    )
                    if not authorization_response_raw:
                        break

                    message = json.loads(authorization_response_raw.decode().strip())
                    log_stratum_message(
                        logger, message, f"Received post-auth message: {message}"
                    )

                    pool_session.pre_auth_messages.append(message)
                    message_count += 1

                    if message.get("id") == authorization_id:
                        authorization_response = message

                    # Stop after auth response + mining.notify (initial job)
                    if authorization_response and message_count > 1:
                        break

                except asyncio.TimeoutError:
                    if authorization_response:
                        logger.warning(
                            "Timeout waiting for initial job, proceeding anyway"
                        )
                        break
                    else:
                        raise RuntimeError(
                            "Timeout waiting for authorization response from pool"
                        )

            if authorization_response is None:
                raise RuntimeError("Did not receive authorization response from pool")

            error = authorization_response.get("error")
            if error:
                error_message = f"Pool auth failed: {error}"
                logger.error(error_message)
                raise RuntimeError(error_message)

            logger.info("Pool authorization successful")
            return pool_session

        except Exception as exception:
            logger.error(f"Failed to connect to pool: {exception}")
            raise
