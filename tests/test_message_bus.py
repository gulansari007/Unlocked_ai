import asyncio
import unittest
from agents.message_bus import AgentMessageBus, AgentMessage

class TestAgentMessageBus(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bus = AgentMessageBus()

    async def test_agent_registration(self):
        await self.bus.register_agent("test_agent")
        # Accessing private queue list for verification
        self.assertIn("test_agent", self.bus._queues)
        await self.bus.unregister_agent("test_agent")
        self.assertNotIn("test_agent", self.bus._queues)

    async def test_request_response_flow(self):
        # We need a recipient task to listen and reply
        async def mock_recipient_listener():
            # Await incoming message
            req_msg = await self.bus.get_message("agent_b")
            self.assertEqual(req_msg.content, "Hello from A")
            self.assertEqual(req_msg.sender, "agent_a")
            # Send reply
            await self.bus.send_response(req_msg, "Hi back from B")

        # Start recipient listener
        listener_task = asyncio.create_task(mock_recipient_listener())

        # Sender sends message and blocks awaiting response
        resp_msg = await self.bus.send_message(
            sender="agent_a",
            recipient="agent_b",
            content="Hello from A"
        )

        self.assertEqual(resp_msg.content, "Hi back from B")
        self.assertEqual(resp_msg.sender, "agent_b")
        self.assertEqual(resp_msg.recipient, "agent_a")
        self.assertTrue(resp_msg.is_response)

        # Cleanup listener task
        await listener_task

if __name__ == "__main__":
    unittest.main()
