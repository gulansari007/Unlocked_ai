import os
import sys
import json
import asyncio
import logging
from typing import Optional

try:
    import websockets
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.prompt import Prompt, Confirm
    from rich.theme import Theme
    from rich.text import Text
except ImportError:
    print("Missing dependencies. Please run 'pip install -r requirements.txt' first.")
    sys.exit(1)

# Custom Rich Theme for premium terminal look
custom_theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "error": "bold red",
    "agent_name": "bold purple",
    "tool_name": "bold yellow",
    "thought": "italic white",
    "success": "bold green",
})

console = Console(theme=custom_theme)

async def main(ws_url: str = "ws://127.0.0.1:8000/ws"):
    # Print a premium, colored ASCII art title
    console.print()
    console.print("[bold purple]  _    _ _   _ _      ____   _____ _  __ ______ _____       _______ [/bold purple]")
    console.print("[bold purple] | |  | | \\ | | |    / __ \\ / ____| |/ /|  ____|  __ \\     |__   __|[/bold purple]")
    console.print("[bold purple] | |  | |  \\| | |   | |  | | |    | ' / | |__  | |  | |  __ _ | |   [/bold purple]")
    console.print("[bold cyan] | |  | | . ` | |   | |  | | |    |  <  |  __| | |  | | / _` || |   [/bold cyan]")
    console.print("[bold cyan] | |__| | |\\  | |___| |__| | |____| . \\ | |____| |__| || (_| || |   [/bold cyan]")
    console.print("[bold cyan]  \\____/|_| \\_|______\\____/ \\_____|_|\\_\\|______|_____/  \\__,_||_|   [/bold cyan]")
    console.print()

    console.print(Panel(
        "[bold white]⚡ Unified Developer Dashboard & Agentic Framework ⚡[/bold white]\n"
        "[dim]Interactive shell client connecting to Unlocked AI Core Server[/dim]",
        border_style="purple",
        title="[bold purple]v0.1.0[/bold purple]",
        title_align="right"
    ))
    console.print()

    # Test/Establish WebSocket connection
    try:
        async with websockets.connect(ws_url) as ws:

            console.print("[success]✓ Connected to Unlocked AI Core Server[/success]\n")
            
            # Read initialization message
            init_msg = await ws.recv()
            init_data = json.loads(init_msg)
            current_provider = init_data.get("current_provider", "default")
            console.print(f"[info]Active Provider Override: {current_provider}[/info]")

            while True:
                try:
                    # Request prompt from user
                    prompt_text = Prompt.ask("\n[bold purple]Unlocked AI[/bold purple] >")
                    prompt_text = prompt_text.strip()
                    if not prompt_text:
                        continue
                    
                    if prompt_text.lower() in ("exit", "quit"):
                        console.print("[info]Exiting client. Goodbye![/info]")
                        break

                    # Send request to agent server
                    await ws.send(json.dumps({
                        "type": "run_agent",
                        "content": prompt_text
                    }))

                    # Enter execution loop, receiving status events in real-time
                    is_running = True
                    while is_running:
                        msg_str = await ws.recv()
                        msg = json.loads(msg_str)
                        msg_type = msg.get("type")
                        data = msg.get("data", {})

                        if msg_type == "status":
                            # If running goes to False, execution finished
                            if msg.get("running") is False:
                                is_running = False

                        elif msg_type == "thought":
                            agent = data.get("agent", "coordinator")
                            content = data.get("content", "")
                            
                            # Render thought box in markdown
                            console.print(Panel(
                                Markdown(content),
                                title=f"[agent_name]{agent.upper()} Thought[/agent_name]",
                                border_style="purple",
                                padding=(1, 2)
                            ))

                        elif msg_type == "log":
                            level = data.get("level", "INFO")
                            message = data.get("message", "")
                            
                            # Skip internal websocket loop logs
                            if "/ws" in message or "WebSocket" in message:
                                continue

                            style = "info"
                            if level == "WARNING":
                                style = "warning"
                            elif level == "ERROR":
                                style = "error"
                            
                            console.print(f"[dim font-mono][{level}][/dim font-mono] {message}", style=style)

                        elif msg_type == "tool_start":
                            tool = data.get("tool", "")
                            arguments = data.get("arguments", {})
                            console.print(f"\n[info]🛠️ Starting tool:[/info] [tool_name]{tool}[/tool_name]")
                            console.print(f"[dim font-mono]Args: {json.dumps(arguments)}[/dim font-mono]")

                        elif msg_type == "tool_end":
                            tool = data.get("tool", "")
                            output = data.get("output", "")
                            console.print(f"[success]✅ Completed tool:[/success] [tool_name]{tool}[/tool_name]")
                            # Truncate large tool output in CLI to avoid cluttering
                            short_output = output[:500] + "\n... [truncated]" if len(output) > 500 else output
                            console.print(Panel(short_output, title="Tool Output", border_style="dim green"))

                        elif msg_type == "terminal_output":
                            content = data.get("content", "")
                            # Print terminal outputs natively
                            sys.stdout.write(content)
                            sys.stdout.flush()

                        elif msg_type == "approval_request":
                            prompt_id = msg.get("prompt_id")
                            agent = msg.get("agent", "coordinator")
                            tool = msg.get("tool", "")
                            arguments = msg.get("arguments", {})

                            console.print(Panel(
                                f"[warning]Mutating Action Requested by Agent: {agent.upper()}[/warning]\n"
                                f"Tool: [tool_name]{tool}[/tool_name]\n"
                                f"Arguments:\n{json.dumps(arguments, indent=2)}",
                                title="⚠️ HUMAN APPROVAL REQUIRED",
                                border_style="yellow",
                                padding=(1, 2)
                            ))

                            approved = Confirm.ask("[bold yellow]Approve execution?[/bold yellow]")
                            feedback = ""
                            if not approved:
                                feedback = Prompt.ask("[bold red]Enter rejection feedback / corrections[/bold red]")

                            # Send response back to server
                            await ws.send(json.dumps({
                                "type": "approval_response",
                                "prompt_id": prompt_id,
                                "approved": approved,
                                "feedback": feedback
                            }))

                        elif msg_type == "agent_response":
                            content = msg.get("content", "")
                            console.print("\n" + "="*40)
                            console.print(Panel(
                                Markdown(content),
                                title="🔮 FINAL AGENT RESPONSE",
                                border_style="green",
                                padding=(1, 2)
                            ))
                            console.print("="*40)
                            is_running = False

                except websockets.ConnectionClosed:
                    console.print("[error]Connection to server lost. Reconnect to resume.[/error]")
                    break
                except KeyboardInterrupt:
                    console.print("\n[warning]Execution interrupted by user (Ctrl+C).[/warning]")
                    # Try to notify server to stop execution
                    break

    except (OSError, websockets.InvalidMessage) as e:
        console.print(
            f"[error]Error: Could not connect to Core Agent Server at {ws_url}.[/error]\n"
            f"[info]Please make sure the FastAPI server is running. Start it by running:\n"
            f"  unlocked start[/info]"
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting. Goodbye!")
        sys.exit(0)
