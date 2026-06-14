import logging
from typing import Any, Dict, List, Optional
import httpx

from agents.base import BaseAgent
from providers.base import ChatMessage
from tools.base import BaseTool, ToolRegistry, ExecutionMode

logger = logging.getLogger(__name__)

class WebFetchTool(BaseTool):
    """
    Downloads external HTTP web page contents.
    Allowed in PLAN and BUILD modes.
    """
    def __init__(self):
        super().__init__(
            name="fetch_url",
            description="Downloads raw text content from an external URL.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The absolute URL to download content from."}
                },
                "required": ["url"]
            },
            required_mode=ExecutionMode.PLAN
        )

    async def execute(self, url: str, **kwargs: Any) -> str:
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                headers = {
                    "User-Agent": "UnlockedAI-Agent/1.0 (Autonomous Web Fetcher)"
                }
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                text = response.text
                
                # Truncate content length to prevent model context blast
                if len(text) > 10000:
                    text = text[:10000] + "\n\n... [Content Truncated by Fetcher for Token Safety]"
                return text
        except Exception as e:
            return f"Error fetching url {url}: {str(e)}"

class WebFetcherAgent(BaseAgent):
    """
    Peer agent specializing in fetching external documentation, web pages, or crawling resources.
    Operates strictly in PLAN mode.
    """
    def __init__(self, router, message_bus):
        registry = ToolRegistry()
        registry.register(WebFetchTool())

        system_instruction = (
            "You are Unlocked AI's Web Fetcher Agent. Your task is to scrape, fetch, or summarize "
            "external web resources and API documentations. Use the 'fetch_url' tool to retrieve "
            "contents from URLs requested by the coordinator. Clean up the response and return "
            "a concise summary of the key information found."
        )
        super().__init__(
            role="fetcher",
            router=router,
            message_bus=message_bus,
            tools_registry=registry,
            mode=ExecutionMode.PLAN,
            system_instruction=system_instruction
        )

    async def process_request(self, content: str) -> str:
        messages = [
            ChatMessage(role="user", content=f"Please fetch and summarize information from: {content}")
        ]
        response = await self.run_llm_loop(messages)
        return response.content or "No web content retrieved."
