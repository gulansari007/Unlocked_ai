# Unlocked AI ⚡

Unlocked AI is a premium Developer Dashboard and orchestration framework built with **FastAPI**, **Material 3 Design System**, and **Agentic AI**. It allows you to run multiple LLM providers, delegate coding/context tasks to specialized peer agents, run an isolated persistent shell, and automate daily life/productivity workflows.

---

## Key Features 🚀

- **Core Orchestration Agent**: A coordinator agent that can toggle between `PLAN` (read-only) and `BUILD` (mutating) phases.
- **Peer Subagents**: Dedicated agents for specialized jobs:
  - `Code Reviewer`: Static analysis and security reviewer.
  - `Context Scout`: Greps and scopes project files.
  - `Web Fetcher`: Crawls external developer documentation.
- **Isolated Terminal**: A persistent PowerShell shell session embedded directly into the workspace.
- **Multi-Provider Routing**: Instantly configure and switch LLM providers (Google Gemini, Groq, OpenRouter, OpenAI, Anthropic, or local Ollama).
- **Daily Reminders ⏰**:
  - Set custom alert timers (recurring or one-off) to remind you to drink water, stand up, stretch, etc.
  - Real-time WebSocket delivery with HTML5 browser push notifications, sound chimes (Web Audio API), and dashboard logs.
- **Productivity Hub 🎯**:
  - **Pomodoro Timer**: Work focus intervals (25m Focus / 5m Break / Custom) ticking in real-time.
  - **Task Board**: A persistent todo checklist saved to `.unlocked_todos.json` in your workspace.
- **Telegram Bot Remote Control 🤖**:
  - Connect a Telegram Bot to receive notifications, request human approval for mutating shell commands, or chat with the agent on the go.

---

## Installation & Setup 💻

Follow these commands in your terminal to set up and run Unlocked AI:

### 1. Initialize Virtual Environment

```bash
# Navigate to project directory
cd Unlockedd_ai

# Create a virtual environment
python -m venv venv

# Activate the virtual environment (Windows)
venv\Scripts\activate

# Activate the virtual environment (macOS/Linux)
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Configuration Wizard

Unlocked AI includes an interactive onboarding CLI wizard to securely save your API keys and configuration to a local `.env` file:

```bash
python -m server.cli onboard
```

---

## Running the Application ⚙️

### Start the Dashboard Server

```bash
python -m server.cli start --host 127.0.0.1 --port 8000
```
Once started, the Material 3 Developer Dashboard will be available at:
👉 **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

### Run Terminal Chat Client

If you prefer to chat with the agent directly from your terminal, execute:

```bash
python -m server.cli chat
```

---

## Agent-Driven Productivity Commands 🔮

Because the agent is fully integrated with the scheduler and productivity managers, you can issue conversational instructions in the agent console:

- **Scheduling Reminders**:
  - *"remind me to drink water every 20 minutes"*
  - *"set a one-off reminder in 5 minutes to check the server logs"*
- **Managing Tasks**:
  - *"add a todo task to refactor the agent base class"*
  - *"list all my active todos"*
- **Timer Control**:
  - *"start a pomodoro break timer for 5 minutes"*
  - *"stop my active pomodoro"*