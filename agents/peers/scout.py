import logging
from typing import List, Optional
from agents.base import BaseAgent
from providers.base import ChatMessage
from tools.base import ToolRegistry, ExecutionMode
from tools.system import ReadFileTool, ListDirTool, SearchGrepTool

logger = logging.getLogger(__name__)

class ContextScoutAgent(BaseAgent):
    """
    Peer agent specializing in crawling files, listing workspace directories, 
    and searching codebase symbols. Operates in PLAN mode.
    """
    def __init__(self, router, message_bus):
        # Scout is equipped with read-only tools
        registry = ToolRegistry()
        registry.register(ReadFileTool())
        registry.register(ListDirTool())
        registry.register(SearchGrepTool())

        system_instruction = (
            "You are Unlocked AI's Context Scout Agent. Your role is to inspect the workspace "
            "and locate files, folders, code structures, import paths, or specific text queries. "
            "You have access to tools to read files, list directories, and search/grep patterns. "
            "Use these tools strategically to answer questions about the repository structure and "
            "locate exactly what the user or coordinator requests. Return a summary of your findings."
        )
        super().__init__(
            role="scout",
            router=router,
            message_bus=message_bus,
            tools_registry=registry,
            mode=ExecutionMode.PLAN,
            system_instruction=system_instruction
        )

    async def process_request(self, content: str) -> str:
        messages = [
            ChatMessage(role="user", content=f"Please locate or inspect context for: {content}")
        ]
        response = await self.run_llm_loop(messages)
        return response.content or "No scout search results generated."
