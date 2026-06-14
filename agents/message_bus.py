import asyncio
import logging
import uuid
from typing import Dict, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class AgentMessage(BaseModel):
    """
    Structured message payload for inter-agent communication.
    """
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    sender: str
    recipient: str
    content: str
    is_response: bool = False

class AgentMessageBus:
    """
    Zero-polling local message broker using asyncio.Queue.
    Supports asynchronous RPC-like request-reply communication between subagents.
    """
    def __init__(self):
        self._queues: Dict[str, asyncio.Queue[AgentMessage]] = {}
        self._pending_futures: Dict[str, asyncio.Future[AgentMessage]] = {}
        self._lock = asyncio.Lock()

    async def register_agent(self, role: str) -> None:
        async with self._lock:
            if role not in self._queues:
                self._queues[role] = asyncio.Queue()
                logger.info(f"Registered mail queue for agent role: '{role}'")

    async def unregister_agent(self, role: str) -> None:
        async with self._lock:
            if role in self._queues:
                del self._queues[role]
                logger.info(f"Unregistered mail queue for agent role: '{role}'")

    async def send_message(self, sender: str, recipient: str, content: str) -> AgentMessage:
        """
        Sends a request message and suspends execution until a response is received back.
        Resolves via asyncio.Future (zero polling).
        """
        # Ensure recipient is registered or has a queue ready
        await self.register_agent(recipient)
        
        correlation_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        
        async with self._lock:
            self._pending_futures[correlation_id] = future

        msg = AgentMessage(
            correlation_id=correlation_id,
            sender=sender,
            recipient=recipient,
            content=content,
            is_response=False
        )

        logger.debug(f"[{sender} -> {recipient}] Enqueuing message (correlation_id={correlation_id})")
        await self._queues[recipient].put(msg)

        try:
            # Block until the response is sent back
            response_msg = await future
            logger.debug(f"[{sender} <- {recipient}] Future resolved for correlation_id={correlation_id}")
            return response_msg
        finally:
            async with self._lock:
                self._pending_futures.pop(correlation_id, None)

    async def send_response(self, original_msg: AgentMessage, content: str) -> None:
        """
        Responds to a received request message, resolving the sender's pending future.
        """
        recipient = original_msg.sender
        correlation_id = original_msg.correlation_id

        if not correlation_id:
            logger.warning(f"Attempted to reply to a message without correlation_id (sender={original_msg.sender})")
            return

        response_msg = AgentMessage(
            correlation_id=correlation_id,
            sender=original_msg.recipient,
            recipient=recipient,
            content=content,
            is_response=True
        )

        # Resolve the pending future directly if present in the active loop
        async with self._lock:
            future = self._pending_futures.get(correlation_id)
            
        if future and not future.done():
            future.set_result(response_msg)
        else:
            # Fallback to enqueuing if the sender is not checking a local future
            await self.register_agent(recipient)
            await self._queues[recipient].put(response_msg)

    async def get_message(self, role: str) -> AgentMessage:
        """
        Blocks asynchronously until a message is available for the given agent role.
        Zero CPU consumption while waiting.
        """
        await self.register_agent(role)
        return await self._queues[role].get()
