import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from agents.events import event_bus

logger = logging.getLogger("server.productivity")

# File path for persistent todos
TODOS_FILE = os.path.join(os.getcwd(), ".unlocked_todos.json")

class TodoItem:
    """
    Represents an individual task on the user's Todo List.
    """
    def __init__(self, id: str, text: str, completed: bool = False, created_at: Optional[str] = None):
        self.id = id
        self.text = text
        self.completed = completed
        self.created_at = created_at or datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "completed": self.completed,
            "created_at": self.created_at
        }

class TodoManager:
    """
    Loads, saves, and mutates Todo task entries persisted to .unlocked_todos.json.
    """
    def __init__(self, file_path: str = TODOS_FILE):
        self.file_path = file_path
        self.todos: Dict[str, TodoItem] = {}
        self.load()

    def load(self):
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        todo = TodoItem(
                            id=item["id"],
                            text=item["text"],
                            completed=item.get("completed", False),
                            created_at=item.get("created_at")
                        )
                        self.todos[todo.id] = todo
                logger.info(f"Loaded {len(self.todos)} todos from {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to load todos: {e}")

    def save(self):
        try:
            data = [todo.to_dict() for todo in self.todos.values()]
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save todos: {e}")

    def get_all(self) -> List[Dict[str, Any]]:
        # Return sorted by created_at desc (newest tasks first)
        items = list(self.todos.values())
        items.sort(key=lambda x: x.created_at, reverse=True)
        return [todo.to_dict() for todo in items]

    def add(self, text: str) -> Dict[str, Any]:
        import uuid
        todo_id = str(uuid.uuid4())
        todo = TodoItem(id=todo_id, text=text)
        self.todos[todo_id] = todo
        self.save()
        logger.info(f"Added todo {todo_id}: '{text}'")
        # Broadcast updated todos list to frontends
        event_bus.emit("todos_updated", self.get_all())
        return todo.to_dict()

    def toggle(self, todo_id: str) -> Optional[Dict[str, Any]]:
        if todo_id in self.todos:
            todo = self.todos[todo_id]
            todo.completed = not todo.completed
            self.save()
            logger.info(f"Toggled todo {todo_id} to completed={todo.completed}")
            # Broadcast updated todos list to frontends
            event_bus.emit("todos_updated", self.get_all())
            return todo.to_dict()
        return None

    def delete(self, todo_id: str) -> bool:
        if todo_id in self.todos:
            del self.todos[todo_id]
            self.save()
            logger.info(f"Deleted todo {todo_id}")
            # Broadcast updated todos list to frontends
            event_bus.emit("todos_updated", self.get_all())
            return True
        return False


class PomodoroManager:
    """
    Manages background Pomodoro timer tasks, ticking down and emitting websocket events.
    """
    def __init__(self, tg_bot=None):
        self.tg_bot = tg_bot
        self.task: Optional[asyncio.Task] = None
        self.session_type: str = "focus"  # "focus" or "break"
        self.total_seconds: int = 0
        self.remaining_seconds: int = 0
        self.active: bool = False

    def start(self, duration_minutes: float, session_type: str = "focus") -> Dict[str, Any]:
        self.stop()  # Stop any active timer
        
        self.session_type = session_type
        self.total_seconds = int(duration_minutes * 60)
        self.remaining_seconds = self.total_seconds
        self.active = True
        
        self.task = asyncio.create_task(self._run_loop())
        logger.info(f"Started Pomodoro {session_type} session for {duration_minutes} minutes.")
        # Broadcast active state immediately to UI
        event_bus.emit("pomodoro_tick", self.get_status())
        return self.get_status()

    def stop(self) -> bool:
        if self.task:
            self.task.cancel()
            self.task = None
        
        was_active = self.active
        self.active = False
        self.total_seconds = 0
        self.remaining_seconds = 0
        
        if was_active:
            logger.info("Stopped Pomodoro session.")
            # Broadcast the stop to clear the UI timer
            event_bus.emit("pomodoro_tick", self.get_status())
            return True
        return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "active": self.active,
            "session_type": self.session_type,
            "total_seconds": self.total_seconds,
            "remaining_seconds": self.remaining_seconds
        }

    async def _run_loop(self):
        try:
            while self.active and self.remaining_seconds > 0:
                # Emit update tick every second
                event_bus.emit("pomodoro_tick", self.get_status())
                await asyncio.sleep(1.0)
                self.remaining_seconds -= 1
            
            if self.active and self.remaining_seconds <= 0:
                self.active = False
                event_bus.emit("pomodoro_complete", {
                    "session_type": self.session_type,
                    "message": f"Pomodoro {self.session_type} session completed!"
                })
                logger.info(f"Pomodoro {self.session_type} session completed!")
                
                # Send Alert via Telegram Bot
                if self.tg_bot:
                    try:
                        asyncio.create_task(self.tg_bot.send_reminder_notification(
                            f"🍅 *Pomodoro Complete!*\nYour {self.session_type} session is finished."
                        ))
                    except Exception as e:
                        logger.error(f"Failed to send Pomodoro Telegram alert: {e}")
        except asyncio.CancelledError:
            pass
        finally:
            self.active = False
            self.task = None


# Export default singleton instances
todo_manager = TodoManager()
pomodoro_manager = PomodoroManager()
