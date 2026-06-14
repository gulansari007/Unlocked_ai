import os
import json
import asyncio
import logging
from typing import Optional, Dict, Any
import httpx

from config.settings import settings
from agents.coordinator import CoordinatorAgent
from tools.base import ExecutionMode

logger = logging.getLogger("server.telegram")

class TelegramBotService:
    """
    Background service that connects Unlocked AI to Telegram using long-polling.
    Supports chat commands, text reasoning loops, and interactive tool approvals via inline buttons.
    """
    def __init__(self, coordinator: CoordinatorAgent, pending_approvals: dict):
        self.coordinator = coordinator
        self.pending_approvals = pending_approvals
        self.offset = 0
        self.task: Optional[asyncio.Task] = None
        self.running = False
        # Store Telegram chat IDs that have initiated commands to relay approvals to them
        self.chat_ids = set()

    def start(self):
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self._poll_loop())
            logger.info("Telegram Bot background loop started.")

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            logger.info("Telegram Bot background loop stopped.")

    async def _send_message(self, chat_id: int, text: str, reply_markup: Optional[dict] = None) -> bool:
        token = settings.telegram_bot_token
        if not token:
            return False
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    # Retry without Markdown if syntax failed
                    payload.pop("parse_mode", None)
                    await client.post(url, json=payload)
                return True
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    async def send_approval_request(self, prompt_id: str, agent: str, tool: str, arguments: dict):
        """Relays a tool approval request to all registered Telegram chat sessions."""
        if not self.chat_ids:
            return

        args_str = json.dumps(arguments, indent=2)
        text = (
            f"⚠️ *HUMAN APPROVAL REQUIRED*\n\n"
            f"*Agent:* {agent.upper()}\n"
            f"*Tool:* `{tool}`\n"
            f"*Arguments:*\n```json\n{args_str}\n```\n\n"
            f"Please approve or reject this action:"
        )

        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "Approve ✅", "callback_data": f"app_{prompt_id}"},
                    {"text": "Reject ❌", "callback_data": f"rej_{prompt_id}"}
                ]
            ]
        }

        for chat_id in list(self.chat_ids):
            await self._send_message(chat_id, text, reply_markup)

    async def send_reminder_notification(self, text: str):
        """Relays a reminder message to all active chat sessions."""
        if not self.chat_ids:
            return
        
        text_msg = f"⏰ *REMINDER:*\n{text}"
        for chat_id in list(self.chat_ids):
            await self._send_message(chat_id, text_msg)

    async def _handle_callback_query(self, query: dict):
        chat_id = query["message"]["chat"]["id"]
        query_id = query["id"]
        data: str = query["data"]
        token = settings.telegram_bot_token

        # Answer query to remove loading spinner in Telegram app
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                    json={"callback_query_id": query_id}
                )
        except Exception:
            pass

        approved = data.startswith("app_")
        prompt_id = data.split("_", 1)[1]

        future = self.pending_approvals.get(prompt_id)
        if future and not future.done():
            # Resolve the approval future
            feedback = "" if approved else "Rejected by user via Telegram."
            future.set_result((approved, feedback))
            
            status_text = "Approved! Execution resuming..." if approved else "Action Rejected."
            await self._send_message(chat_id, f"ℹ️ {status_text}")
            
            # Edit original message to remove buttons
            try:
                orig_text = query["message"]["text"]
                edit_url = f"https://api.telegram.org/bot{token}/editMessageText"
                edit_payload = {
                    "chat_id": chat_id,
                    "message_id": query["message"]["message_id"],
                    "text": f"{orig_text}\n\n*Selection:* " + ("Approved ✅" if approved else "Rejected ❌")
                }
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(edit_url, json=edit_payload)
            except Exception as e:
                logger.error(f"Error updating inline keyboard: {e}")
        else:
            await self._send_message(chat_id, "⚠️ This action has already been resolved or expired.")

    async def _handle_text_message(self, chat_id: int, text: str):
        self.chat_ids.add(chat_id)

        if text.startswith("/start") or text.startswith("/help"):
            welcome = (
                "⚡ *Unlocked AI Telegram Agent* ⚡\n\n"
                "I am connected directly to your computer environment.\n"
                "Ask me to write code, manage files, search the web, list running processes, or execute CLI tasks.\n\n"
                "_*Note:* Any system mutating tool calls will send an interactive approval button directly here before execution._"
            )
            await self._send_message(chat_id, welcome)
            return

        # Tell user we are working
        await self._send_message(chat_id, "🔮 *Thinking...*")

        try:
            # Run coordinator agent
            self.coordinator.set_mode(ExecutionMode.BUILD)
            response = await self.coordinator.process_request(text)
            
            # Escape markdown highlights
            clean_resp = response.replace("_", "\\_").replace("*", "\\*")
            # Restore proper markdown blocks
            clean_resp = clean_resp.replace("\\*\\*", "**").replace("\\_\\_", "__")
            
            await self._send_message(chat_id, clean_resp)
        except Exception as e:
            logger.error(f"Error processing Telegram prompt: {e}")
            await self._send_message(chat_id, f"❌ *Error running agent:* {str(e)}")

    async def _poll_loop(self):
        while self.running:
            token = settings.telegram_bot_token
            if not token or token.startswith("mock_"):
                # No token configured, sleep and check again later
                await asyncio.sleep(5.0)
                continue

            url = f"https://api.telegram.org/bot{token}/getUpdates"
            params = {
                "offset": self.offset,
                "timeout": 20
            }

            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        updates = data.get("result", [])
                        
                        for update in updates:
                            self.offset = update["update_id"] + 1
                            
                            # Handle Callback query (Buttons)
                            if "callback_query" in update:
                                await self._handle_callback_query(update["callback_query"])
                                
                            # Handle Text Messages
                            elif "message" in update and "text" in update["message"]:
                                chat_id = update["message"]["chat"]["id"]
                                msg_text = update["message"]["text"]
                                asyncio.create_task(self._handle_text_message(chat_id, msg_text))
                                
                    elif resp.status_code == 401:
                        logger.error("Telegram API Token is invalid (401). Please check settings.")
                        await asyncio.sleep(15.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Telegram polling error: {e}")
                await asyncio.sleep(5.0)
