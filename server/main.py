import os
import sys
import json
import uuid
import logging
import asyncio
from typing import Dict, Any, Tuple, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config.settings import settings
from config.providers import PROVIDERS
from agents.coordinator import CoordinatorAgent
from agents.peers.reviewer import CodeReviewerAgent
from agents.peers.scout import ContextScoutAgent
from agents.peers.fetcher import WebFetcherAgent
from agents.message_bus import AgentMessageBus
from providers.router import MultiProviderRouter
from tools.base import ExecutionMode
from agents.events import event_bus, LogBroadcastHandler
from server.shell import PersistentShell
from server.telegram_bot import TelegramBotService
from server.scheduler import reminder_scheduler
from server.productivity import todo_manager, pomodoro_manager


# Set up logging with our custom broadcast handler
logging.basicConfig(level=logging.INFO)
root_logger = logging.getLogger()
log_handler = LogBroadcastHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler.setFormatter(formatter)
root_logger.addHandler(log_handler)

logger = logging.getLogger("server.main")

# Initialize core frameworks
message_bus = AgentMessageBus()
router = MultiProviderRouter()

# Initialize Agents
coordinator = CoordinatorAgent(router, message_bus)
reviewer = CodeReviewerAgent(router, message_bus)
scout = ContextScoutAgent(router, message_bus)
fetcher = WebFetcherAgent(router, message_bus)

# Create Persistent Shell
shell = PersistentShell(initial_cwd=os.getcwd())

# Inject Persistent Shell into Coordinator's execute_command tool
try:
    exec_tool = coordinator.tools_registry.get_tool("execute_command", ExecutionMode.BUILD)
    exec_tool.shell = shell
    logger.info("Successfully injected PersistentShell into Coordinator's execute_command tool.")
except Exception as e:
    logger.error(f"Failed to inject shell into execute_command tool: {e}")

# Pending approval futures
pending_approvals: Dict[str, asyncio.Future] = {}

# Create Telegram Bot Service
tg_bot = TelegramBotService(coordinator, pending_approvals)


# Set up the approval hook on the coordinator
async def request_approval_hook(agent_role: str, tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, str]:
    prompt_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    pending_approvals[prompt_id] = future

    # Broadcast approval request to all frontends
    payload = {
        "type": "approval_request",
        "prompt_id": prompt_id,
        "agent": agent_role,
        "tool": tool_name,
        "arguments": arguments
    }
    await broadcast_message(payload)
    
    # Send approval request to Telegram bot
    asyncio.create_task(tg_bot.send_approval_request(prompt_id, agent_role, tool_name, arguments))


    logger.info(f"Suspending agent execution waiting for approval of '{tool_name}' (prompt_id: {prompt_id})")
    try:
        approved, feedback = await future
        logger.info(f"Resuming agent execution for prompt_id: {prompt_id}. Approved: {approved}")
        return approved, feedback
    finally:
        pending_approvals.pop(prompt_id, None)

coordinator.approval_hook = request_approval_hook

# FastAPI Application setup
app = FastAPI(title="Unlocked AI Core Server")

# Allow CORS for easy debugging
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active connections list
active_connections: Set[WebSocket] = set()

async def broadcast_message(message: dict):
    """Sends a JSON message to all active WebSocket clients."""
    msg_str = json.dumps(message)
    for conn in list(active_connections):
        try:
            await conn.send_text(msg_str)
        except Exception:
            active_connections.discard(conn)

# Route event bus entries directly to the Websocket stream
async def on_agent_event(event_type: str, data: Any):
    await broadcast_message({
        "type": event_type,
        "data": data
    })

event_bus.register_listener(on_agent_event)

# Startup and Shutdown management
@app.on_event("startup")
async def startup_event():
    # Start message bus listeners for the subagents
    await reviewer.start()
    await scout.start()
    await fetcher.start()
    # Start persistent shell
    await shell.start()
    # Start Telegram Bot Service
    tg_bot.start()
    # Inject Telegram Bot into reminder scheduler and pomodoro manager
    reminder_scheduler.tg_bot = tg_bot
    pomodoro_manager.tg_bot = tg_bot
    logger.info("Unlocked AI Server started and agents initialized.")

@app.on_event("shutdown")
async def shutdown_event():
    await reviewer.stop()
    await scout.stop()
    await fetcher.stop()
    await shell.stop()
    # Stop Telegram Bot Service
    await tg_bot.stop()
    # Cancel all pending reminders and pomodoro sessions
    reminder_scheduler.clear()
    pomodoro_manager.stop()
    logger.info("Unlocked AI Server stopped cleanly.")



# REST API Endpoints

class FileWriteRequest(BaseModel):
    path: str
    content: str

class ReminderAddRequest(BaseModel):
    message: str
    interval_minutes: float
    is_recurring: bool = True

class ReminderCancelRequest(BaseModel):
    reminder_id: str

class TodoAddRequest(BaseModel):
    text: str

class TodoToggleRequest(BaseModel):
    todo_id: str

class TodoDeleteRequest(BaseModel):
    todo_id: str

class PomodoroStartRequest(BaseModel):
    duration_minutes: float
    session_type: str = "focus"

class ProviderSelectRequest(BaseModel):
    provider_model: str

class SettingsSaveRequest(BaseModel):
    openrouter_api_key: Optional[str] = None
    opencode_api_key: Optional[str] = None
    opencode_base_url: Optional[str] = None
    ollama_base_url: Optional[str] = None
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    anthropic_base_url: Optional[str] = None
    telegram_bot_token: Optional[str] = None



def get_directory_tree(path: str) -> list:
    tree = []
    try:
        for entry in os.scandir(path):
            if entry.name in (".git", "venv", ".venv", "__pycache__", "node_modules", ".gemini", ".vscode"):
                continue
            
            relative_path = os.path.relpath(entry.path, start=os.getcwd()).replace("\\", "/")
            if entry.is_dir():
                children = get_directory_tree(entry.path)
                tree.append({
                    "name": entry.name,
                    "path": relative_path,
                    "type": "directory",
                    "children": children
                })
            else:
                tree.append({
                    "name": entry.name,
                    "path": relative_path,
                    "type": "file"
                })
    except Exception as e:
        logger.error(f"Error scanning directory {path}: {e}")
    
    # Sort folders first, then files
    tree.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))
    return tree

@app.get("/api/reminders")
async def api_get_reminders():
    """Returns all active reminders."""
    return reminder_scheduler.get_all_reminders()

@app.post("/api/reminders/add")
async def api_add_reminder(payload: ReminderAddRequest):
    """Adds a new reminder."""
    reminder = reminder_scheduler.add_reminder(
        message=payload.message,
        interval_minutes=payload.interval_minutes,
        is_recurring=payload.is_recurring
    )
    return {
        "status": "success",
        "reminder": {
            "id": reminder.id,
            "message": reminder.message,
            "interval_minutes": reminder.interval_minutes,
            "is_recurring": reminder.is_recurring
        }
    }

@app.post("/api/reminders/cancel")
async def api_cancel_reminder(payload: ReminderCancelRequest):
    """Cancels an existing reminder."""
    success = reminder_scheduler.cancel_reminder(payload.reminder_id)
    if not success:
        raise HTTPException(status_code=404, detail="Reminder not found or already completed.")
    return {"status": "success"}

@app.get("/api/todos")
async def api_get_todos():
    """Returns all todo tasks."""
    return todo_manager.get_all()

@app.post("/api/todos/add")
async def api_add_todo(payload: TodoAddRequest):
    """Adds a new todo task."""
    return todo_manager.add(payload.text)

@app.post("/api/todos/toggle")
async def api_toggle_todo(payload: TodoToggleRequest):
    """Toggles a todo task completion status."""
    todo = todo_manager.toggle(payload.todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Task not found.")
    return todo

@app.post("/api/todos/delete")
async def api_delete_todo(payload: TodoDeleteRequest):
    """Deletes a todo task."""
    success = todo_manager.delete(payload.todo_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found.")
    return {"status": "success"}

@app.get("/api/pomodoro")
async def api_get_pomodoro():
    """Returns the current Pomodoro timer status."""
    return pomodoro_manager.get_status()

@app.post("/api/pomodoro/start")
async def api_start_pomodoro(payload: PomodoroStartRequest):
    """Starts a Pomodoro focus or break session."""
    return pomodoro_manager.start(
        duration_minutes=payload.duration_minutes,
        session_type=payload.session_type
    )

@app.post("/api/pomodoro/stop")
async def api_stop_pomodoro():
    """Stops the active Pomodoro session."""
    pomodoro_manager.stop()
    return {"status": "success"}

@app.get("/api/files")
async def api_get_files():
    """Returns the workspace directory tree."""
    return get_directory_tree(os.getcwd())

@app.get("/api/file/read")
async def api_read_file(path: str):
    """Reads a file from the workspace."""
    abs_path = os.path.abspath(path)
    if not abs_path.startswith(os.getcwd()):
        raise HTTPException(status_code=403, detail="Access denied. Path outside workspace.")
    
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/file/write")
async def api_write_file(payload: FileWriteRequest):
    """Writes content to a file in the workspace."""
    abs_path = os.path.abspath(payload.path)
    if not abs_path.startswith(os.getcwd()):
        raise HTTPException(status_code=403, detail="Access denied. Path outside workspace.")
    
    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(payload.content)
        return {"status": "success", "path": payload.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/providers")
async def api_get_providers():
    """Lists LLM providers configurations and active status."""
    providers_list = []
    for key, val in PROVIDERS.items():
        is_configured = settings.is_provider_configured(key)
        # Ollama is local, we allow it even if not explicitly defined in env keys
        if key == "ollama":
            is_configured = True
        
        providers_list.append({
            "id": key,
            "name": val.name,
            "configured": is_configured,
            "default_model": val.default_model,
            "available_models": val.available_models
        })
    
    return {
        "providers": providers_list,
        "current_provider": router.override_model or "default"
    }


@app.post("/api/providers/select")
async def api_select_provider(payload: ProviderSelectRequest):
    """Selects the dynamic override provider/model."""
    if payload.provider_model == "default":
        router.override_model = None
    else:
        router.override_model = payload.provider_model
    
    await broadcast_message({
        "type": "provider_updated",
        "current_provider": payload.provider_model
    })
    return {"status": "success", "current_provider": payload.provider_model}

@app.get("/api/config")
async def api_get_config():
    """Returns the current settings keys masked for security."""
    def mask(val: Optional[str]) -> str:
        if not val or val.startswith("mock_"):
            return ""
        return "••••••••"

    return {
        "openrouter_api_key": mask(settings.openrouter_api_key),
        "opencode_api_key": mask(settings.opencode_api_key),
        "opencode_base_url": settings.opencode_base_url or "",
        "ollama_base_url": settings.ollama_base_url or "",
        "gemini_api_key": mask(settings.gemini_api_key),
        "groq_api_key": mask(settings.groq_api_key),
        "openai_api_key": mask(settings.openai_api_key),
        "openai_base_url": settings.openai_base_url or "",
        "anthropic_api_key": mask(settings.anthropic_api_key),
        "anthropic_base_url": settings.anthropic_base_url or "",
        "telegram_bot_token": mask(settings.telegram_bot_token)
    }



@app.post("/api/config/save")
async def api_save_config(payload: SettingsSaveRequest):
    """Saves updated settings values to the settings object and writes to .env."""
    env_path = os.path.join(os.getcwd(), ".env")
    updates = {}
    
    if payload.openrouter_api_key is not None and payload.openrouter_api_key != "••••••••":
        settings.openrouter_api_key = payload.openrouter_api_key
        updates["OPENROUTER_API_KEY"] = payload.openrouter_api_key
        
    if payload.opencode_api_key is not None and payload.opencode_api_key != "••••••••":
        settings.opencode_api_key = payload.opencode_api_key
        updates["OPENCODE_API_KEY"] = payload.opencode_api_key

    if payload.opencode_base_url is not None:
        settings.opencode_base_url = payload.opencode_base_url
        updates["OPENCODE_BASE_URL"] = payload.opencode_base_url

    if payload.ollama_base_url is not None:
        settings.ollama_base_url = payload.ollama_base_url
        updates["OLLAMA_BASE_URL"] = payload.ollama_base_url

    if payload.gemini_api_key is not None and payload.gemini_api_key != "••••••••":
        settings.gemini_api_key = payload.gemini_api_key
        updates["GEMINI_API_KEY"] = payload.gemini_api_key

    if payload.groq_api_key is not None and payload.groq_api_key != "••••••••":
        settings.groq_api_key = payload.groq_api_key
        updates["GROQ_API_KEY"] = payload.groq_api_key

    if payload.openai_api_key is not None and payload.openai_api_key != "••••••••":
        settings.openai_api_key = payload.openai_api_key
        updates["OPENAI_API_KEY"] = payload.openai_api_key

    if payload.openai_base_url is not None:
        settings.openai_base_url = payload.openai_base_url
        updates["OPENAI_BASE_URL"] = payload.openai_base_url

    if payload.anthropic_api_key is not None and payload.anthropic_api_key != "••••••••":
        settings.anthropic_api_key = payload.anthropic_api_key
        updates["ANTHROPIC_API_KEY"] = payload.anthropic_api_key

    if payload.anthropic_base_url is not None:
        settings.anthropic_base_url = payload.anthropic_base_url
        updates["ANTHROPIC_BASE_URL"] = payload.anthropic_base_url

    if payload.telegram_bot_token is not None and payload.telegram_bot_token != "••••••••":
        settings.telegram_bot_token = payload.telegram_bot_token
        updates["TELEGRAM_BOT_TOKEN"] = payload.telegram_bot_token



    # Write back to .env preserving comments and lines
    try:
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        
        new_lines = []
        replaced_keys = set()
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, v = stripped.split("=", 1)
                k = k.strip()
                if k in updates:
                    new_lines.append(f"{k}={updates[k]}\n")
                    replaced_keys.add(k)
                    continue
            new_lines.append(line)
        
        for k, v in updates.items():
            if k not in replaced_keys:
                new_lines.append(f"{k}={v}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    except Exception as e:
        logger.error(f"Error writing .env: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save .env file: {str(e)}")

    # Clear provider client cache
    router._clients.clear()
    
    # Broadcast notice that config was updated
    await broadcast_message({"type": "config_updated"})
    
    logger.info("Dynamic settings saved and LLM clients cleared.")
    return {"status": "success"}


# WebSocket Handler

async def run_agent_task(content: str):
    """Task to run coordinator request loop in the background."""
    await broadcast_message({"type": "status", "running": True})
    try:
        # Run coordinator in BUILD mode to support dynamic execution
        coordinator.set_mode(ExecutionMode.BUILD)
        response = await coordinator.process_request(content)
        await broadcast_message({"type": "agent_response", "content": response})
    except Exception as e:
        logger.error(f"Error running coordinator loop: {e}", exc_info=True)
        await broadcast_message({"type": "agent_response", "content": f"Error running agent: {str(e)}"})
    finally:
        await broadcast_message({"type": "status", "running": False})

async def run_terminal_command(command: str):
    """Runs a command on the unified shell and broadcasts output."""
    try:
        async for chunk in shell.execute(command):
            # Emitting terminal output event broadcasts it to all frontends
            event_bus.emit("terminal_output", {"content": chunk})
    except Exception as e:
        event_bus.emit("terminal_output", {"content": f"Error: {str(e)}\n"})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    
    # Initialize connection state
    await websocket.send_json({
        "type": "init",
        "current_provider": router.override_model or "default",
        "cwd": shell.cwd
    })
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                msg_type = payload.get("type")
                
                if msg_type == "run_agent":
                    content = payload.get("content")
                    asyncio.create_task(run_agent_task(content))
                    
                elif msg_type == "terminal_input":
                    command = payload.get("command")
                    asyncio.create_task(run_terminal_command(command))
                    
                elif msg_type == "approval_response":
                    prompt_id = payload.get("prompt_id")
                    approved = payload.get("approved", False)
                    feedback = payload.get("feedback", "")
                    
                    future = pending_approvals.get(prompt_id)
                    if future and not future.done():
                        future.set_result((approved, feedback))
                        
                elif msg_type == "set_provider":
                    provider_model = payload.get("provider_model")
                    if provider_model == "default":
                        router.override_model = None
                    else:
                        router.override_model = provider_model
                    await broadcast_message({
                        "type": "provider_updated",
                        "current_provider": provider_model
                    })
            except json.JSONDecodeError:
                logger.warning("Received invalid JSON payload from websocket client.")
            except Exception as e:
                logger.error(f"Error processing websocket event: {e}")
    except WebSocketDisconnect:
        pass
    finally:
        active_connections.discard(websocket)

# Mount the static files UI directory at root path
# Check if static folder exists, create if not
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # Listen on localhost port 8000
    uvicorn.run("server.main:app", host="127.0.0.1", port=8000, log_level="info")
