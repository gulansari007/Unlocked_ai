import logging
from typing import List, Optional
from agents.base import BaseAgent
from providers.base import ChatMessage
from tools.base import ToolRegistry, ExecutionMode

logger = logging.getLogger(__name__)

class CodeReviewerAgent(BaseAgent):
    """
    Peer agent specializing in reviewing code changes, diffs, and scripts.
    Operates strictly in PLAN (read-only) mode.
    """
    def __init__(self, router, message_bus):
        # Reviewer doesn't need custom tools of its own; works on text inputs
        registry = ToolRegistry()
        system_instruction = (
            "You are Unlocked AI's Code Reviewer Agent. Your purpose is to inspect proposed "
            "code changes, git diffs, or file contents. Analyze them for syntax errors, logical bugs, "
            "security flaws, styling inconsistencies, and performance anti-patterns. Provide a clean, "
            "concise Markdown report of your findings. Always act constructively."
        )
        super().__init__(
            role="reviewer",
            router=router,
            message_bus=message_bus,
            tools_registry=registry,
            mode=ExecutionMode.PLAN,
            system_instruction=system_instruction
        )

    async def process_request(self, content: str) -> str:
        messages = [
            ChatMessage(role="user", content=f"Please review the following code changes/diff:\n\n{content}")
        ]
        # Run standard LLM completion loop (no tools registered for this agent, just direct reasoning)
        response = await self.run_llm_loop(messages)
        return response.content or "No review response generated."
