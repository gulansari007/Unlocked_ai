import os
import sys
import argparse
import asyncio
import logging
from typing import Optional

# Setup basic logging
logging.basicConfig(level=logging.WARNING)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.theme import Theme
except ImportError:
    print("Please install requirements first: pip install -r requirements.txt")
    sys.exit(1)

# Initialize console
custom_theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "error": "bold red",
    "success": "bold green",
    "primary": "bold purple",
})
console = Console(theme=custom_theme)

# Load existing values helper
def get_env_values() -> dict:
    values = {}
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    values[k.strip()] = v.strip()
    return values

# Save values helper
def save_env_values(updates: dict):
    env_path = os.path.join(os.getcwd(), ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    replaced_keys = set()
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _ = stripped.split("=", 1)
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


def onboard_wizard():
    console.print(Panel.fit(
        "[bold purple]== Unlocked AI Onboarding Setup ==[/bold purple]\n"
        "[dim]Quick wizard to configure LLM API keys and backend options.[/dim]",
        border_style="purple"
    ))

    current = get_env_values()
    updates = {}

    def prompt_key(var_name: str, label: str, help_text: str = ""):
        curr_val = current.get(var_name, "")
        masked_curr = "********" if curr_val else "None"
        prompt_label = f"{label} ({help_text})" if help_text else label
        
        entered = Prompt.ask(
            f"[bold purple]{prompt_label}[/bold purple] [dim](Current: {masked_curr})[/dim]",
            default="",
            show_default=False
        ).strip()
        
        if entered:
            updates[var_name] = entered
        elif curr_val:
            updates[var_name] = curr_val

    def prompt_text(var_name: str, label: str, default_val: str):
        curr_val = current.get(var_name, default_val)
        entered = Prompt.ask(
            f"[bold purple]{label}[/bold purple]",
            default=curr_val
        ).strip()
        updates[var_name] = entered

    console.print("\n[info]=== Native Free Tiers & Standard APIs ===[/info]")
    prompt_key("GEMINI_API_KEY", "Google Gemini API Key", "from Google AI Studio")
    prompt_key("GROQ_API_KEY", "Groq API Key", "from Groq Console")
    prompt_key("OPENAI_API_KEY", "OpenAI API Key", "from OpenAI Platform")
    prompt_text("OPENAI_BASE_URL", "OpenAI Base URL", "https://api.openai.com/v1")
    prompt_key("ANTHROPIC_API_KEY", "Anthropic API Key", "from Anthropic Console")
    prompt_text("ANTHROPIC_BASE_URL", "Anthropic Base URL", "https://api.anthropic.com/v1")
    prompt_key("TELEGRAM_BOT_TOKEN", "Telegram Bot Token", "optional token from @BotFather")


    console.print("\n[info]=== Aggregators & Proxy Services ===[/info]")
    prompt_key("OPENROUTER_API_KEY", "OpenRouter API Key", "from OpenRouter.ai")
    prompt_text("OLLAMA_BASE_URL", "Ollama Local Base URL", "http://localhost:11434")
    prompt_key("OPENCODE_API_KEY", "OpenCode API Key", "optional code model proxy")
    prompt_text("OPENCODE_BASE_URL", "OpenCode Base URL", "https://api.opencode.example.com/v1")

    # Confirm and save
    console.print("\n" + "="*40)
    save = Confirm.ask("[bold yellow]Save these settings to .env?[/bold yellow]")
    if save:
        save_env_values(updates)
        console.print("[success][*] Configuration successfully saved to .env![/success]\n")
    else:
        console.print("[warning]Setup cancelled. Settings not saved.[/warning]\n")


def start_server(host: str, port: int):
    import uvicorn
    console.print(f"[success][Starting] Unlocked AI Core Server on {host}:{port}...[/success]")
    console.print(f"[info]Dashboard will be available at: http://{host}:{port}/[/info]")
    uvicorn.run("server.main:app", host=host, port=port, log_level="info")



def run_cli_client(host: str, port: int):
    import unlocked_cli
    ws_url = f"ws://{host}:{port}/ws"
    try:
        asyncio.run(unlocked_cli.main(ws_url))
    except KeyboardInterrupt:
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Unlocked AI CLI tool — manage backend server, configure APIs, or chat in the terminal.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start the Unlocked AI backend server & dashboard")
    start_parser.add_argument("--host", default="127.0.0.1", help="Host address to bind to (default: 127.0.0.1)")
    start_parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")

    # Chat command
    chat_parser = subparsers.add_parser("chat", aliases=["cli"], help="Start the interactive terminal chat client")
    chat_parser.add_argument("--host", default="127.0.0.1", help="Core Server host address (default: 127.0.0.1)")
    chat_parser.add_argument("--port", type=int, default=8000, help="Core Server port (default: 8000)")

    # Onboard command
    subparsers.add_parser("onboard", help="Run the interactive setup onboarding wizard")

    # Version command
    subparsers.add_parser("version", help="Show current version")

    args = parser.parse_args()

    if args.command == "start":
        start_server(args.host, args.port)
    elif args.command in ("chat", "cli"):
        run_cli_client(args.host, args.port)
    elif args.command == "onboard":
        onboard_wizard()
    elif args.command == "version":
        console.print("[primary]Unlocked AI v0.1.0[/primary]")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
