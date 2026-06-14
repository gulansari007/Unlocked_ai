import os
import sys
import json
import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

# Force UTF-8 output on Windows so Unicode box-drawing characters render correctly
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    import websockets
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.prompt import Prompt, Confirm
    from rich.theme import Theme
    from rich.text import Text
    from rich.align import Align
    from rich.columns import Columns
    from rich.rule import Rule
    from rich.table import Table
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.style import Style
    from rich.padding import Padding
    from rich import box
    from rich.markup import escape
except ImportError:
    print("Missing dependencies. Please run 'pip install -r requirements.txt' first.")
    sys.exit(1)

# ─────────────────────────────────────────────
#  THEME
# ─────────────────────────────────────────────
custom_theme = Theme({
    "primary":      "bold #b06aff",
    "accent":       "bold #00d4ff",
    "success":      "bold #00ff99",
    "warning":      "bold #ffcc00",
    "error":        "bold #ff4444",
    "muted":        "dim #888888",
    "agent":        "bold #cc99ff",
    "tool":         "bold #ffd700",
    "user_msg":     "bold #ffffff",
    "ai_response":  "#e0d0ff",
    "info":         "#7ec8e3",
})

console = Console(theme=custom_theme, highlight=False, force_terminal=True)

# ─────────────────────────────────────────────
#  BANNER FRAMES (animated)
# ─────────────────────────────────────────────
BANNER_LINES = [
    " ██╗   ██╗███╗   ██╗██╗      ██████╗  ██████╗██╗  ██╗███████╗██████╗ ",
    " ██║   ██║████╗  ██║██║     ██╔═══██╗██╔════╝██║ ██╔╝██╔════╝██╔══██╗",
    " ██║   ██║██╔██╗ ██║██║     ██║   ██║██║     █████╔╝ █████╗  ██║  ██║",
    " ╚██████╔╝██║ ╚████║███████╗╚██████╔╝╚██████╗██║  ██╗███████╗██████╔╝",
    "  ╚═════╝ ╚═╝  ╚═══╝╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝╚═════╝ ",
    "",
    "               A G E N T I C   A I   F R A M E W O R K               ",
]

BANNER_COLORS = [
    "#b06aff",
    "#9055e0",
    "#9055e0",
    "#00d4ff",
    "#00d4ff",
    "#ffffff",
    "#888888",
]

def print_banner():
    """Print the animated startup banner."""
    console.print()
    for line, color in zip(BANNER_LINES, BANNER_COLORS):
        console.print(f"[bold {color}]{line}[/bold {color}]", justify="center")
    console.print()


def print_welcome_panel():
    """Print the styled welcome panel below the banner."""
    now = datetime.now().strftime("%A, %B %d %Y  ·  %I:%M %p")

    grid = Table.grid(expand=True)
    grid.add_column(justify="left")
    grid.add_column(justify="right")
    grid.add_row(
        "[primary]⚡ Unlocked AI  [muted]v0.1.0[/muted][/primary]",
        f"[muted]{now}[/muted]"
    )
    grid.add_row(
        "[muted]Agentic Framework · Multi-Provider · WebSocket Shell[/muted]",
        "[accent]● LIVE[/accent]"
    )

    console.print(Panel(
        grid,
        border_style="#5a2d8c",
        padding=(0, 2),
    ))
    console.print()


def print_help():
    """Print a styled help / command reference table."""
    table = Table(
        title="  Available Commands",
        title_style="primary",
        box=box.ROUNDED,
        border_style="#5a2d8c",
        show_header=True,
        header_style="bold #00d4ff",
        expand=False,
        padding=(0, 1),
    )
    table.add_column("Command", style="tool", no_wrap=True)
    table.add_column("Description", style="muted")

    table.add_row("/help",    "Show this command reference")
    table.add_row("/status",  "Show current provider & model")
    table.add_row("/clear",   "Clear the terminal screen")
    table.add_row("/compact", "Toggle compact output mode")
    table.add_row("exit · quit", "Disconnect and exit")

    console.print(Padding(table, (0, 2)))
    console.print()


def print_divider(label: str = "", color: str = "#5a2d8c"):
    console.print(Rule(label, style=color))


def make_user_bubble(text: str) -> Panel:
    return Panel(
        f"[user_msg]{escape(text)}[/user_msg]",
        title="[bold #ffffff]  You[/bold #ffffff]",
        title_align="right",
        border_style="#444466",
        padding=(0, 2),
    )


def make_ai_bubble(content: str) -> Panel:
    return Panel(
        Markdown(content),
        title="[primary]🔮  Unlocked AI[/primary]",
        title_align="left",
        border_style="#7a3fc0",
        padding=(1, 2),
    )


def make_thought_panel(agent: str, content: str) -> Panel:
    return Panel(
        Markdown(content),
        title=f"[agent]💭  {agent.upper()} · Thinking[/agent]",
        title_align="left",
        border_style="dim #9055e0",
        padding=(0, 2),
    )


def make_tool_panel(tool: str, args: dict) -> Panel:
    args_text = json.dumps(args, indent=2) if args else "{}"
    return Panel(
        f"[muted]{escape(args_text)}[/muted]",
        title=f"[tool]🛠️  {tool}[/tool]",
        title_align="left",
        border_style="dim #8a7000",
        padding=(0, 2),
    )


def make_tool_result_panel(tool: str, output: str) -> Panel:
    short = output[:600] + "\n[muted]… (truncated)[/muted]" if len(output) > 600 else output
    return Panel(
        f"[muted]{escape(short)}[/muted]",
        title=f"[success]✅  {tool} · Result[/success]",
        title_align="left",
        border_style="dim #007a44",
        padding=(0, 2),
    )


def make_approval_panel(agent: str, tool: str, args: dict) -> Panel:
    args_text = json.dumps(args, indent=2)
    return Panel(
        f"[warning]Agent  :[/warning]  [agent]{agent.upper()}[/agent]\n"
        f"[warning]Tool   :[/warning]  [tool]{tool}[/tool]\n\n"
        f"[muted]{escape(args_text)}[/muted]",
        title="[warning]⚠️  HUMAN APPROVAL REQUIRED[/warning]",
        title_align="left",
        border_style="yellow",
        padding=(1, 2),
    )


async def spinner_recv(ws, spinner_label: str):
    """Show a live spinner while waiting for a websocket message."""
    spinner = Spinner("dots", style="primary")
    with Live(
        Align.left(Text.assemble(spinner, " ", (spinner_label, "muted"))),
        console=console,
        refresh_per_second=12,
        transient=True,
    ):
        msg_str = await ws.recv()
    return msg_str


# ─────────────────────────────────────────────
#  MAIN CHAT LOOP
# ─────────────────────────────────────────────
async def main(ws_url: str = "ws://127.0.0.1:8000/ws"):

    # ── Animated startup ──────────────────────
    print_banner()
    print_welcome_panel()

    console.print(Align.center("[muted]Type [bold white]/help[/bold white] for commands · [bold white]exit[/bold white] to quit[/muted]\n"))

    compact_mode = False

    # ── WebSocket connection ──────────────────
    try:
        async with websockets.connect(ws_url) as ws:

            console.print(Align.center("[success]◉  Connected to Unlocked AI Core Server[/success]"))
            console.print()

            # Read initialization message
            init_msg = await ws.recv()
            try:
                init_data = json.loads(init_msg)
                current_provider = init_data.get("current_provider", "default")
                console.print(f"[info]  Provider Override: [bold]{current_provider}[/bold][/info]")
            except Exception:
                pass

            console.print()
            print_divider("  CHAT SESSION  ", color="#5a2d8c")
            console.print()

            while True:
                try:
                    # ── User Input ─────────────────────────────
                    user_input = Prompt.ask(
                        "\n[bold #b06aff]◆ You[/bold #b06aff]",
                    ).strip()

                    if not user_input:
                        continue

                    # ── Built-in commands ──────────────────────
                    if user_input.lower() in ("exit", "quit"):
                        console.print()
                        console.print(Align.center("[primary]👋  Session ended. Goodbye![/primary]"))
                        console.print()
                        break

                    if user_input.lower() == "/help":
                        print_help()
                        continue

                    if user_input.lower() == "/clear":
                        console.clear()
                        print_banner()
                        print_welcome_panel()
                        continue

                    if user_input.lower() == "/compact":
                        compact_mode = not compact_mode
                        state = "ON" if compact_mode else "OFF"
                        console.print(f"[info]  Compact mode: [bold]{state}[/bold][/info]")
                        continue

                    if user_input.lower() == "/status":
                        status_table = Table(box=box.SIMPLE, border_style="#5a2d8c", padding=(0,1))
                        status_table.add_column("", style="muted")
                        status_table.add_column("", style="accent")
                        status_table.add_row("Server", ws_url)
                        status_table.add_row("Provider", current_provider if 'current_provider' in dir() else "—")
                        status_table.add_row("Compact", "Yes" if compact_mode else "No")
                        console.print(Padding(status_table, (0, 2)))
                        continue

                    # Echo user bubble
                    console.print(make_user_bubble(user_input))

                    # ── Send to agent ──────────────────────────
                    await ws.send(json.dumps({
                        "type": "run_agent",
                        "content": user_input
                    }))

                    # ── Event loop ─────────────────────────────
                    is_running = True
                    thinking_shown = False

                    while is_running:
                        # Show spinner only while waiting for first event
                        if not thinking_shown:
                            msg_str = await spinner_recv(ws, "Unlocked AI is thinking…")
                            thinking_shown = True
                        else:
                            msg_str = await ws.recv()

                        msg = json.loads(msg_str)
                        msg_type = msg.get("type")
                        data = msg.get("data", {})

                        # ── status ─────────────────────────────
                        if msg_type == "status":
                            if msg.get("running") is False:
                                is_running = False

                        # ── thought ────────────────────────────
                        elif msg_type == "thought":
                            if not compact_mode:
                                agent = data.get("agent", "coordinator")
                                content = data.get("content", "")
                                console.print(make_thought_panel(agent, content))

                        # ── log ────────────────────────────────
                        elif msg_type == "log":
                            level = data.get("level", "INFO")
                            message = data.get("message", "")
                            if "/ws" in message or "WebSocket" in message:
                                continue
                            if not compact_mode:
                                style_map = {"WARNING": "warning", "ERROR": "error"}
                                style = style_map.get(level, "muted")
                                console.print(f"  [{style}][{level}][/{style}] [muted]{escape(message)}[/muted]")

                        # ── tool_start ─────────────────────────
                        elif msg_type == "tool_start":
                            tool = data.get("tool", "")
                            arguments = data.get("arguments", {})
                            console.print(make_tool_panel(tool, arguments))

                        # ── tool_end ───────────────────────────
                        elif msg_type == "tool_end":
                            tool = data.get("tool", "")
                            output = data.get("output", "")
                            if not compact_mode:
                                console.print(make_tool_result_panel(tool, output))
                            else:
                                console.print(f"  [success]✅[/success] [tool]{tool}[/tool] [muted]completed[/muted]")

                        # ── terminal_output ────────────────────
                        elif msg_type == "terminal_output":
                            content = data.get("content", "")
                            sys.stdout.write(content)
                            sys.stdout.flush()

                        # ── approval_request ───────────────────
                        elif msg_type == "approval_request":
                            prompt_id = msg.get("prompt_id")
                            agent = msg.get("agent", "coordinator")
                            tool = msg.get("tool", "")
                            arguments = msg.get("arguments", {})

                            console.print(make_approval_panel(agent, tool, arguments))
                            approved = Confirm.ask("[bold yellow]  Approve execution?[/bold yellow]")
                            feedback = ""
                            if not approved:
                                feedback = Prompt.ask("[bold red]  Enter correction / feedback[/bold red]")

                            await ws.send(json.dumps({
                                "type": "approval_response",
                                "prompt_id": prompt_id,
                                "approved": approved,
                                "feedback": feedback
                            }))

                        # ── agent_response ─────────────────────
                        elif msg_type == "agent_response":
                            content = msg.get("content", "")
                            console.print()
                            console.print(make_ai_bubble(content))
                            console.print()
                            print_divider(color="#333355")
                            is_running = False

                except websockets.ConnectionClosed:
                    console.print()
                    console.print(Align.center("[error]✗  Connection to server lost.[/error]"))
                    break
                except KeyboardInterrupt:
                    console.print()
                    console.print(Align.center("[warning]⚠  Interrupted (Ctrl+C). Session ended.[/warning]"))
                    break

    except (OSError, websockets.InvalidMessage, Exception) as e:
        console.print()
        console.print(Panel(
            f"[error]Could not connect to Core Agent Server at:[/error]\n"
            f"[accent]{ws_url}[/accent]\n\n"
            f"[muted]Make sure the server is running first:[/muted]\n"
            f"[tool]  unlocked start[/tool]\n\n"
            f"[muted]Error: {escape(str(e))}[/muted]",
            title="[error]⚠  Connection Failed[/error]",
            border_style="red",
            padding=(1, 3),
        ))
        console.print()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print()
        console.print(Align.center("[muted]Goodbye! 👋[/muted]"))
        console.print()
        sys.exit(0)
