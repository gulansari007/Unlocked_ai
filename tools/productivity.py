from typing import Any, Dict, Optional
from tools.base import BaseTool, ExecutionMode
from server.productivity import todo_manager, pomodoro_manager

class ManageTodosTool(BaseTool):
    """
    Tool to manage user todo/task boards.
    Requires BUILD mode.
    """
    def __init__(self):
        super().__init__(
            name="manage_todos",
            description=(
                "Manages the user's personal task/todo list. You can add tasks, "
                "toggle task completion, delete tasks, or list all existing tasks."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["add", "toggle", "delete", "list"],
                        "description": "Action to perform: 'add' to create, 'toggle' to check/uncheck, 'delete' to remove, or 'list' to view todos."
                    },
                    "text": {
                        "type": "string",
                        "description": "The text description of the task (required for 'add')."
                    },
                    "todo_id": {
                        "type": "string",
                        "description": "The unique task ID to toggle or delete (required for 'toggle' and 'delete')."
                    }
                },
                "required": ["action"]
            },
            required_mode=ExecutionMode.BUILD
        )

    async def execute(
        self,
        action: str,
        text: Optional[str] = None,
        todo_id: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        if action == "add":
            if not text:
                return "Error: 'text' is required when action is 'add'."
            todo = todo_manager.add(text)
            return f"Successfully added task:\n- ID: {todo['id']}\n- Task: '{todo['text']}'"
            
        elif action == "toggle":
            if not todo_id:
                return "Error: 'todo_id' is required when action is 'toggle'."
            todo = todo_manager.toggle(todo_id)
            if todo:
                status = "completed" if todo["completed"] else "incomplete"
                return f"Successfully toggled task '{todo['text']}' to {status}."
            return f"Error: Task with ID '{todo_id}' not found."
            
        elif action == "delete":
            if not todo_id:
                return "Error: 'todo_id' is required when action is 'delete'."
            success = todo_manager.delete(todo_id)
            if success:
                return f"Successfully deleted task with ID: {todo_id}"
            return f"Error: Task with ID '{todo_id}' not found."
            
        elif action == "list":
            todos = todo_manager.get_all()
            if not todos:
                return "The task list is currently empty."
            lines = ["Current Task Board:"]
            for t in todos:
                marker = "[x]" if t["completed"] else "[ ]"
                lines.append(f"- {marker} ID: {t['id']} | '{t['text']}'")
            return "\n".join(lines)
            
        return f"Error: Unknown action '{action}'."


class ManagePomodoroTool(BaseTool):
    """
    Tool to start, stop, or check status of Pomodoro sessions.
    Requires BUILD mode.
    """
    def __init__(self):
        super().__init__(
            name="manage_pomodoro",
            description=(
                "Manages Pomodoro focus sessions and timers. You can start a new "
                "timer, stop a running timer, or query the active timer's state."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop", "status"],
                        "description": "Action to perform: 'start' to run a session, 'stop' to cancel, or 'status' to check progress."
                    },
                    "duration_minutes": {
                        "type": "number",
                        "description": "Duration of the focus/break session in minutes (required for 'start'). E.g., 25 for focus, 5 for break."
                    },
                    "session_type": {
                        "type": "string",
                        "enum": ["focus", "break"],
                        "description": "Type of session: 'focus' for work, 'break' for resting. Defaults to 'focus'."
                    }
                },
                "required": ["action"]
            },
            required_mode=ExecutionMode.BUILD
        )

    async def execute(
        self,
        action: str,
        duration_minutes: Optional[float] = None,
        session_type: str = "focus",
        **kwargs: Any
    ) -> str:
        if action == "start":
            if duration_minutes is None:
                return "Error: 'duration_minutes' is required when action is 'start'."
            if duration_minutes <= 0:
                return "Error: 'duration_minutes' must be a positive number."
            
            status = pomodoro_manager.start(duration_minutes, session_type)
            return (
                f"Successfully started Pomodoro {session_type} session!\n"
                f"- Duration: {duration_minutes} minutes\n"
                f"- Ticks and alerts will stream to the dashboard in real-time."
            )
            
        elif action == "stop":
            stopped = pomodoro_manager.stop()
            if stopped:
                return "Successfully stopped active Pomodoro session."
            return "There was no active Pomodoro session running."
            
        elif action == "status":
            status = pomodoro_manager.get_status()
            if not status["active"]:
                return "There is currently no active Pomodoro session."
            
            rem_min = status["remaining_seconds"] // 60
            rem_sec = status["remaining_seconds"] % 60
            return (
                f"Active Pomodoro Session Status:\n"
                f"- Type: {status['session_type'].upper()}\n"
                f"- Remaining Time: {rem_min:02d}:{rem_sec:02d} / {status['total_seconds']//60:02d}:00"
            )
            
        return f"Error: Unknown action '{action}'."
