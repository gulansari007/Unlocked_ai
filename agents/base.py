import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from config.settings import settings
from providers.router import MultiProviderRouter
from providers.base import ChatMessage, ToolDefinition, LLMResponse, ToolCall
from tools.base import ToolRegistry, ExecutionMode
from agents.message_bus import AgentMessageBus, AgentMessage

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """
    Abstract base class for all Unlocked AI agents.
    Provides standard capabilities for receiving message bus requests,
    invoking routed LLMs, and executing local tool operations.
    """
    def __init__(
        self,
        role: str,
        router: MultiProviderRouter,
        message_bus: AgentMessageBus,
        tools_registry: ToolRegistry,
        mode: ExecutionMode = ExecutionMode.PLAN,
        system_instruction: str = ""
    ):
        self.role = role
        self.router = router
        self.message_bus = message_bus
        self.tools_registry = tools_registry
        self.mode = mode
        self.system_instruction = system_instruction
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.approval_hook = None

    async def start(self) -> None:
        """
        Starts the agent's background message queue listener task.
        """
        if self._running:
            return
        self._running = True
        await self.message_bus.register_agent(self.role)
        self._task = asyncio.create_task(self._listen_loop())
        logger.info(f"Agent '{self.role}' started in mode {self.mode}")

    async def _listen_loop(self) -> None:
        while self._running:
            try:
                msg = await self.message_bus.get_message(self.role)
                if msg.is_response:
                    continue  # Awaited futures handle replies directly; bypass main loop
                
                # Execute reasoning block
                logger.info(f"Agent '{self.role}' received request from '{msg.sender}'")
                response_content = await self.process_request(msg.content)
                
                # Send reply back
                await self.message_bus.send_response(msg, response_content)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in agent '{self.role}' listener: {e}", exc_info=True)
                await asyncio.sleep(1) # Backoff to prevent crash loops

    async def stop(self) -> None:
        """
        Gracefully terminates the background listener task.
        """
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.message_bus.unregister_agent(self.role)
        logger.info(f"Agent '{self.role}' stopped.")

    @abstractmethod
    async def process_request(self, content: str) -> str:
        """
        Must be implemented by subclasses to determine agent behavior upon request.
        """
        pass

    async def run_llm_loop(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.5,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Executes a reasoning loop with the LLM. 
        Automatically detects and resolves tool execution calls recursively.
        """
        # Inject system instructions
        has_system = any(m.role == "system" for m in messages)
        if not has_system and self.system_instruction:
            messages.insert(0, ChatMessage(role="system", content=self.system_instruction))

        # Retrieve tools allowed under current execution mode
        tools = self.tools_registry.get_tools_for_mode(self.mode)
        tool_defs = [
            ToolDefinition(name=t.name, description=t.description, parameters=t.parameters)
            for t in tools
        ]

        max_iterations = 10
        for i in range(max_iterations):
            response = await self.router.generate(
                messages=messages,
                model=model,
                tools=tool_defs if tool_defs else None,
                temperature=temperature,
                max_tokens=max_tokens
            )

            from agents.events import event_bus
            if response.content:
                event_bus.emit("thought", {"agent": self.role, "content": response.content})

            if not response.tool_calls:
                return response

            # Save the generation containing tool calls to context history
            assistant_msg = ChatMessage(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls
            )
            messages.append(assistant_msg)

            # Process requested tools sequentially
            for tc in response.tool_calls:
                logger.info(f"Agent '{self.role}' executing tool '{tc.name}' (call_id: {tc.id})")
                try:
                    tool = self.tools_registry.get_tool(tc.name, self.mode)
                    args = json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments
                    
                    # Human-in-the-Loop check
                    approved = True
                    feedback = ""
                    if self.approval_hook:
                        event_bus.emit("tool_approval_pending", {
                            "agent": self.role,
                            "tool": tc.name,
                            "arguments": args
                        })
                        approved, feedback = await self.approval_hook(self.role, tc.name, args)

                    if approved:
                        event_bus.emit("tool_start", {
                            "agent": self.role,
                            "tool": tc.name,
                            "arguments": args
                        })
                        tool_output = await tool.execute(**args)
                    else:
                        tool_output = f"Tool execution rejected by user. Feedback: {feedback}"
                        logger.warning(f"Tool execution rejected by user: {feedback}")
                        
                except PermissionError as pe:
                    tool_output = f"Permission Denied: {str(pe)}"
                    logger.warning(tool_output)
                except Exception as e:
                    tool_output = f"Error executing tool '{tc.name}': {str(e)}"
                    logger.error(tool_output, exc_info=True)

                # Emit tool execution completion
                event_bus.emit("tool_end", {
                    "agent": self.role,
                    "tool": tc.name,
                    "output": tool_output
                })

                # Feed the tool execution results back into the conversation context
                messages.append(
                    ChatMessage(
                        role="tool",
                        name=tc.name,
                        tool_call_id=tc.id,
                        content=tool_output
                    )
                )
        
        raise RuntimeError(f"Agent '{self.role}' exceeded maximum tool iteration depth of {max_iterations}.")
