import logging
from typing import Any, Dict, List, Optional

from agents.base import BaseAgent
from agents.message_bus import AgentMessageBus
from providers.router import MultiProviderRouter
from providers.base import ChatMessage, LLMResponse
from tools.base import BaseTool, ToolRegistry, ExecutionMode
from tools.system import (
    ReadFileTool, ListDirTool, SearchGrepTool, WriteFileTool, PatchFileTool,
    ExecuteCommandTool, StartApplicationTool, ListProcessesTool, KillProcessTool, WebSearchTool
)


logger = logging.getLogger(__name__)

# Peer Delegation Tools
class DelegateReviewerTool(BaseTool):
    """
    Coordinator tool to delegate review tasks to the Code Reviewer.
    """
    def __init__(self, message_bus: AgentMessageBus):
        super().__init__(
            name="delegate_to_reviewer",
            description="Sends code snippets or diff outputs to the Code Reviewer subagent for analysis.",
            parameters={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The exact code content or diff text to review."}
                },
                "required": ["content"]
            },
            required_mode=ExecutionMode.PLAN
        )
        self.message_bus = message_bus

    async def execute(self, content: str, **kwargs: Any) -> str:
        msg = await self.message_bus.send_message(
            sender="coordinator",
            recipient="reviewer",
            content=content
        )
        return msg.content

class DelegateScoutTool(BaseTool):
    """
    Coordinator tool to delegate workspace search tasks to the Context Scout.
    """
    def __init__(self, message_bus: AgentMessageBus):
        super().__init__(
            name="delegate_to_scout",
            description="Asks the Context Scout subagent to find specific file scopes or search symbols in the workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Details of the file, folder name, or string pattern to look up."}
                },
                "required": ["query"]
            },
            required_mode=ExecutionMode.PLAN
        )
        self.message_bus = message_bus

    async def execute(self, query: str, **kwargs: Any) -> str:
        msg = await self.message_bus.send_message(
            sender="coordinator",
            recipient="scout",
            content=query
        )
        return msg.content

class DelegateFetcherTool(BaseTool):
    """
    Coordinator tool to delegate URL fetching tasks to the Web Fetcher.
    """
    def __init__(self, message_bus: AgentMessageBus):
        super().__init__(
            name="delegate_to_fetcher",
            description="Requests the Web Fetcher subagent to crawl a documentation page URL or web content.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The absolute HTTP/HTTPS URL of the target resource."}
                },
                "required": ["url"]
            },
            required_mode=ExecutionMode.PLAN
        )
        self.message_bus = message_bus

    async def execute(self, url: str, **kwargs: Any) -> str:
        msg = await self.message_bus.send_message(
            sender="coordinator",
            recipient="fetcher",
            content=url
        )
        return msg.content


class CoordinatorAgent(BaseAgent):
    """
    Primary orchestration intelligence of the Unlocked AI framework.
    Routes user requests, transitions execution permissions (PLAN vs BUILD), 
    and handles tool-calling hierarchies with peer subagents.
    """
    def __init__(
        self,
        router: MultiProviderRouter,
        message_bus: AgentMessageBus,
        mode: ExecutionMode = ExecutionMode.PLAN
    ):
        registry = ToolRegistry()
        
        # Enforce registration of basic read-only workspace tools (permitted in all modes)
        registry.register(ReadFileTool())
        registry.register(ListDirTool())
        registry.register(SearchGrepTool())
        registry.register(ListProcessesTool())
        registry.register(WebSearchTool())
        
        # Mutating tools (only resolved in BUILD mode during execution runtime)
        registry.register(WriteFileTool())
        registry.register(PatchFileTool())
        registry.register(ExecuteCommandTool())
        registry.register(StartApplicationTool())
        registry.register(KillProcessTool())
        
        # Peer delegation tools
        registry.register(DelegateReviewerTool(message_bus))
        registry.register(DelegateScoutTool(message_bus))
        registry.register(DelegateFetcherTool(message_bus))

        system_instruction = (
            "You are Unlocked AI's Coordinator Agent—the primary intelligence orchestrating system operations.\n"
            "You operates under two distinct permissions modes:\n"
            "1. PLAN: Read-only phase. Ingest context, search directories, and propose blueprint plans. You are strictly forbidden from writing files or executing shell code.\n"
            "2. BUILD: Mutating phase. Apply patches, write scripts, and execute test commands.\n\n"
            "Use your delegation tools to dispatch tasks to peers for optimal context retrieval:\n"
            "- Use 'delegate_to_reviewer' for static analysis or checking script security.\n"
            "- Use 'delegate_to_scout' for finding files or grep searches in the workspace.\n"
            "- Use 'delegate_to_fetcher' for fetching online documentations.\n\n"
            "Analyze requirements, delegate when appropriate, and present structured plans to the user."
        )

        super().__init__(
            role="coordinator",
            router=router,
            message_bus=message_bus,
            tools_registry=registry,
            mode=mode,
            system_instruction=system_instruction
        )

    def set_mode(self, mode: ExecutionMode) -> None:
        """
        Dynamically transition permission modes (PLAN <-> BUILD).
        """
        self.mode = mode
        logger.info(f"Coordinator mode set to: {self.mode}")

    async def process_request(self, content: str) -> str:
        messages = [
            ChatMessage(role="user", content=content)
        ]
        response = await self.run_llm_loop(messages)
        return response.content or "No coordinator response was generated."
