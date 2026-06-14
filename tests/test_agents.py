import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from config.settings import settings
from tools.base import ToolRegistry, ExecutionMode
from agents.message_bus import AgentMessageBus
from agents.coordinator import CoordinatorAgent
from agents.peers.reviewer import CodeReviewerAgent
from agents.peers.scout import ContextScoutAgent
from agents.peers.fetcher import WebFetcherAgent
from providers.router import MultiProviderRouter
from providers.base import LLMResponse, ChatMessage

class TestAgentCoordination(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.message_bus = AgentMessageBus()
        self.mock_router = MagicMock(spec=MultiProviderRouter)
        
        # Instantiate agents
        self.coordinator = CoordinatorAgent(self.mock_router, self.message_bus)
        self.reviewer = CodeReviewerAgent(self.mock_router, self.message_bus)
        self.scout = ContextScoutAgent(self.mock_router, self.message_bus)
        self.fetcher = WebFetcherAgent(self.mock_router, self.message_bus)
        
        # Start background listener loops for worker agents
        await self.reviewer.start()
        await self.scout.start()
        await self.fetcher.start()

    async def asyncTearDown(self):
        # Stop background loops
        await self.reviewer.stop()
        await self.scout.stop()
        await self.fetcher.stop()
        await self.coordinator.stop()

    async def test_reviewer_direct_delegation(self):
        # Setup mock router for reviewer agent call
        self.mock_router.generate = AsyncMock()
        self.mock_router.generate.return_value = LLMResponse(
            content="Code review comments: LGTM!",
            model_name="mock-model"
        )

        # Directly send a message via bus to reviewer
        response_msg = await self.message_bus.send_message(
            sender="coordinator",
            recipient="reviewer",
            content="def add(a, b): return a + b"
        )

        self.assertEqual(response_msg.content, "Code review comments: LGTM!")
        self.assertEqual(response_msg.sender, "reviewer")
        self.mock_router.generate.assert_called_once()

    async def test_scout_direct_delegation(self):
        self.mock_router.generate = AsyncMock()
        self.mock_router.generate.return_value = LLMResponse(
            content="Found target file at config/settings.py",
            model_name="mock-model"
        )

        response_msg = await self.message_bus.send_message(
            sender="coordinator",
            recipient="scout",
            content="Find configuration class settings"
        )

        self.assertEqual(response_msg.content, "Found target file at config/settings.py")
        self.assertEqual(response_msg.sender, "scout")

    async def test_fetcher_direct_delegation(self):
        self.mock_router.generate = AsyncMock()
        self.mock_router.generate.return_value = LLMResponse(
            content="API docs fetched: GET /v1/models resolves list of models.",
            model_name="mock-model"
        )

        response_msg = await self.message_bus.send_message(
            sender="coordinator",
            recipient="fetcher",
            content="https://api.example.com/docs"
        )

        self.assertEqual(response_msg.content, "API docs fetched: GET /v1/models resolves list of models.")
        self.assertEqual(response_msg.sender, "fetcher")

    async def test_coordinator_tool_delegation(self):
        # Testing the tool delegation method directly in coordinator
        self.mock_router.generate = AsyncMock()
        self.mock_router.generate.return_value = LLMResponse(
            content="Review complete.",
            model_name="mock-model"
        )
        
        # Execute the delegation tool registered with the coordinator
        tool = self.coordinator.tools_registry.get_tool("delegate_to_reviewer", ExecutionMode.PLAN)
        res = await tool.execute(content="print('hello')")
        self.assertEqual(res, "Review complete.")

if __name__ == "__main__":
    unittest.main()
