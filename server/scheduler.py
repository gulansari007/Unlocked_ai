import asyncio
import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from agents.events import event_bus

logger = logging.getLogger("server.scheduler")

class Reminder:
    """
    Represents an individual reminder task.
    Supports single execution or recurring intervals.
    """
    def __init__(self, message: str, interval_minutes: float, is_recurring: bool = True):
        self.id = str(uuid.uuid4())
        self.message = message
        self.interval_minutes = interval_minutes
        self.is_recurring = is_recurring
        self.created_at = datetime.utcnow().isoformat()
        self.task: Optional[asyncio.Task] = None
        self.active = True

    def start(self, scheduler_callback):
        self.task = asyncio.create_task(self._run(scheduler_callback))

    async def _run(self, scheduler_callback):
        delay_seconds = self.interval_minutes * 60.0
        try:
            if not self.is_recurring:
                await asyncio.sleep(delay_seconds)
                if self.active:
                    await scheduler_callback(self)
            else:
                while self.active:
                    await asyncio.sleep(delay_seconds)
                    if self.active:
                        await scheduler_callback(self)
        except asyncio.CancelledError:
            pass
        finally:
            self.active = False

    def cancel(self):
        self.active = False
        if self.task:
            self.task.cancel()

class ReminderScheduler:
    """
    Manages scheduling, cancellation, listing, and invocation of reminders.
    """
    def __init__(self, tg_bot=None):
        self.reminders: Dict[str, Reminder] = {}
        self.tg_bot = tg_bot

    def add_reminder(self, message: str, interval_minutes: float, is_recurring: bool = True) -> Reminder:
        reminder = Reminder(message, interval_minutes, is_recurring)
        self.reminders[reminder.id] = reminder
        reminder.start(self._trigger_reminder)
        logger.info(f"Added reminder {reminder.id}: '{message}' every {interval_minutes}m")
        # Broadcast the updated reminders list
        event_bus.emit("reminders_updated", self.get_all_reminders())
        return reminder

    def cancel_reminder(self, reminder_id: str) -> bool:
        if reminder_id in self.reminders:
            self.reminders[reminder_id].cancel()
            del self.reminders[reminder_id]
            logger.info(f"Cancelled reminder {reminder_id}")
            # Broadcast the updated reminders list
            event_bus.emit("reminders_updated", self.get_all_reminders())
            return True
        return False

    def get_all_reminders(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": r.id,
                "message": r.message,
                "interval_minutes": r.interval_minutes,
                "is_recurring": r.is_recurring,
                "created_at": r.created_at,
                "active": r.active
            }
            for r in list(self.reminders.values())
        ]

    def clear(self):
        for reminder in list(self.reminders.values()):
            reminder.cancel()
        self.reminders.clear()
        logger.info("Cleared all active reminders.")

    async def _trigger_reminder(self, reminder: Reminder):
        logger.info(f"⏰ REMINDER TRIGGERED: {reminder.message}")
        
        # Emit event to all connected UI WebSockets via event bus
        event_bus.emit("reminder", {
            "id": reminder.id,
            "message": reminder.message,
            "interval_minutes": reminder.interval_minutes,
            "is_recurring": reminder.is_recurring,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Relay alert to active Telegram sessions
        if self.tg_bot:
            try:
                # Dispatch notification asynchronously
                asyncio.create_task(self.tg_bot.send_reminder_notification(reminder.message))
            except Exception as e:
                logger.error(f"Failed to send Telegram reminder: {e}")

        # If it was a one-off reminder, remove it from dictionary
        if not reminder.is_recurring:
            self.reminders.pop(reminder.id, None)

# Export default singleton instance
reminder_scheduler = ReminderScheduler()
