from typing import Any, Dict, Optional
from tools.base import BaseTool, ExecutionMode
from server.scheduler import reminder_scheduler

class ManageRemindersTool(BaseTool):
    """
    Tool to manage daily reminders (add, cancel, list).
    Requires BUILD mode.
    """
    def __init__(self):
        super().__init__(
            name="manage_reminders",
            description=(
                "Manages user task reminders and alerts. Use this to schedule "
                "daily reminders (e.g., remind to drink water, stand up), list all "
                "currently active reminders, or cancel a reminder."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["add", "cancel", "list"],
                        "description": "Action to perform: 'add' to create a reminder, 'cancel' to stop one, or 'list' to view all active reminders."
                    },
                    "message": {
                        "type": "string",
                        "description": "The description/alert message of the reminder (required for 'add')."
                    },
                    "interval_minutes": {
                        "type": "number",
                        "description": "How often the reminder should fire in minutes (required for 'add'). E.g., 1 for every minute, 60 for hourly."
                    },
                    "is_recurring": {
                        "type": "boolean",
                        "description": "Whether the reminder is recurring or runs only once. Defaults to true."
                    },
                    "reminder_id": {
                        "type": "string",
                        "description": "The unique ID of the reminder to cancel (required for 'cancel')."
                    }
                },
                "required": ["action"]
            },
            required_mode=ExecutionMode.BUILD
        )

    async def execute(
        self,
        action: str,
        message: Optional[str] = None,
        interval_minutes: Optional[float] = None,
        is_recurring: bool = True,
        reminder_id: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        if action == "add":
            if not message:
                return "Error: 'message' is required when action is 'add'."
            if interval_minutes is None:
                return "Error: 'interval_minutes' is required when action is 'add'."
            if interval_minutes <= 0:
                return "Error: 'interval_minutes' must be a positive number."
            
            reminder = reminder_scheduler.add_reminder(
                message=message,
                interval_minutes=interval_minutes,
                is_recurring=is_recurring
            )
            recur_type = "recurring" if is_recurring else "one-off"
            return (
                f"Successfully scheduled a {recur_type} reminder:\n"
                f"- ID: {reminder.id}\n"
                f"- Message: '{reminder.message}'\n"
                f"- Interval: every {reminder.interval_minutes} minutes"
            )
            
        elif action == "cancel":
            if not reminder_id:
                return "Error: 'reminder_id' is required when action is 'cancel'."
            
            success = reminder_scheduler.cancel_reminder(reminder_id)
            if success:
                return f"Successfully cancelled reminder with ID: {reminder_id}"
            else:
                return f"Error: Reminder with ID '{reminder_id}' not found or already completed."
                
        elif action == "list":
            reminders = reminder_scheduler.get_all_reminders()
            if not reminders:
                return "There are currently no active reminders."
            
            lines = ["Active Reminders:"]
            for r in reminders:
                recur_str = "recurring" if r["is_recurring"] else "one-off"
                lines.append(
                    f"- ID: {r['id']} | Message: '{r['message']}' | "
                    f"Interval: every {r['interval_minutes']}m ({recur_str})"
                )
            return "\n".join(lines)
            
        else:
            return f"Error: Unknown action '{action}'."
