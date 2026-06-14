import asyncio
import os
import re
import sys
from typing import Any, Dict, Optional
from tools.base import BaseTool, ExecutionMode

class ReadFileTool(BaseTool):
    """
    Reads contents of a file from disk.
    Allowed in PLAN and BUILD modes.
    """
    def __init__(self):
        super().__init__(
            name="read_file",
            description="Reads the complete contents of a file from the workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path or relative path to the file."}
                },
                "required": ["path"]
            },
            required_mode=ExecutionMode.PLAN
        )

    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file {path}: {str(e)}"

class ListDirTool(BaseTool):
    """
    Lists the contents of a directory.
    Allowed in PLAN and BUILD modes.
    """
    def __init__(self):
        super().__init__(
            name="list_dir",
            description="Lists all files and directories in a given path.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to list contents of. Defaults to current directory."}
                },
                "required": []
            },
            required_mode=ExecutionMode.PLAN
        )

    async def execute(self, path: str = ".", **kwargs: Any) -> str:
        try:
            items = os.listdir(path)
            lines = []
            for item in items:
                full_path = os.path.join(path, item)
                is_dir = os.path.isdir(full_path)
                marker = "[DIR]" if is_dir else "[FILE]"
                size = os.path.getsize(full_path) if not is_dir else 0
                lines.append(f"{marker} {item} ({size} bytes)" if not is_dir else f"{marker} {item}")
            return "\n".join(lines) if lines else "Directory is empty."
        except Exception as e:
            return f"Error listing directory {path}: {str(e)}"

class SearchGrepTool(BaseTool):
    """
    Searches for regular expressions/substrings in the workspace.
    Allowed in PLAN and BUILD modes.
    """
    def __init__(self):
        super().__init__(
            name="grep_search",
            description="Recursively searches for patterns or string matches in files under a directory.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to search within."},
                    "query": {"type": "string", "description": "Text pattern or regex to search for."},
                    "is_regex": {"type": "boolean", "description": "Whether to treat the query as a regex pattern."}
                },
                "required": ["path", "query"]
            },
            required_mode=ExecutionMode.PLAN
        )

    async def execute(self, path: str, query: str, is_regex: bool = False, **kwargs: Any) -> str:
        try:
            flags = re.IGNORECASE
            if is_regex:
                pattern = re.compile(query, flags)
            else:
                pattern = re.compile(re.escape(query), flags)

            results = []
            count = 0
            for root, dirs, files in os.walk(path):
                # Prune common ignore paths
                dirs[:] = [d for d in dirs if d not in (".git", "venv", "__pycache__", "node_modules")]
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            for idx, line in enumerate(f, 1):
                                if pattern.search(line):
                                    results.append(f"{file_path}:{idx}: {line.strip()}")
                                    count += 1
                                    if count >= 100:  # Cap result set for sanity
                                        results.append("... [truncated after 100 matches]")
                                        return "\n".join(results)
                    except Exception:
                        continue
            return "\n".join(results) if results else "No matches found."
        except Exception as e:
            return f"Error executing search query: {str(e)}"

class WriteFileTool(BaseTool):
    """
    Creates or overwrites a file on disk.
    BUILD mode only.
    """
    def __init__(self):
        super().__init__(
            name="write_file",
            description="Creates or overwrites a file with new content. Requires BUILD mode.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to create or overwrite."},
                    "content": {"type": "string", "description": "The exact content to write."}
                },
                "required": ["path", "content"]
            },
            required_mode=ExecutionMode.BUILD
        )

    async def execute(self, path: str, content: str, **kwargs: Any) -> str:
        try:
            # Ensure folder exists
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote file to {path} ({len(content)} bytes)."
        except Exception as e:
            return f"Error writing file to {path}: {str(e)}"

class PatchFileTool(BaseTool):
    """
    Performs precision string edits/replaces inside a file.
    BUILD mode only.
    """
    def __init__(self):
        super().__init__(
            name="patch_file",
            description="Edits a file by replacing a block of target content with new replacement content. Requires BUILD mode.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to edit."},
                    "target": {"type": "string", "description": "The exact block of code to search and replace."},
                    "replacement": {"type": "string", "description": "The new block of code to insert."}
                },
                "required": ["path", "target", "replacement"]
            },
            required_mode=ExecutionMode.BUILD
        )

    async def execute(self, path: str, target: str, replacement: str, **kwargs: Any) -> str:
        try:
            if not os.path.exists(path):
                return f"Error: File '{path}' does not exist."
            
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            if target not in content:
                return f"Error: Target block not found in '{path}'. Please ensure exact whitespace matching."
            
            # Count occurrences
            occurrences = content.count(target)
            if occurrences > 1:
                return f"Error: Target block is not unique. Found {occurrences} occurrences in '{path}'."

            new_content = content.replace(target, replacement, 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"Successfully patched file '{path}' (1 replacement made)."
        except Exception as e:
            return f"Error patching file '{path}': {str(e)}"

class ExecuteCommandTool(BaseTool):
    """
    Runs shell commands asynchronously.
    BUILD mode only.
    """
    def __init__(self):
        super().__init__(
            name="execute_command",
            description="Executes a command shell execution. Requires BUILD mode.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command line to run."},
                    "cwd": {"type": "string", "description": "Directory to run command inside. Defaults to workspace root."}
                },
                "required": ["command"]
            },
            required_mode=ExecutionMode.BUILD
        )
        self.shell = None

    async def execute(self, command: str, cwd: Optional[str] = None, **kwargs: Any) -> str:
        if self.shell:
            try:
                from agents.events import event_bus
                output = []
                async for chunk in self.shell.execute(command):
                    output.append(chunk)
                    event_bus.emit("terminal_output", {"content": chunk})
                
                result = "".join(output)
                return f"Persistent Shell Output:\n{result}"
            except Exception as e:
                return f"Error executing command in persistent shell: {str(e)}"

        try:
            # Setup shell args
            use_shell = True
            
            # Run command asynchronously
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )

            # Wait for execution and read stdout/stderr
            stdout, stderr = await proc.communicate()
            
            stdout_str = stdout.decode("utf-8", errors="ignore")
            stderr_str = stderr.decode("utf-8", errors="ignore")
            
            output = []
            if stdout_str:
                output.append(f"Stdout:\n{stdout_str}")
            if stderr_str:
                output.append(f"Stderr:\n{stderr_str}")
            
            result = "\n".join(output) if output else "Command completed with no output."
            return f"Exit Code: {proc.returncode}\n{result}"
        except Exception as e:
            return f"Error executing command: {str(e)}"

class StartApplicationTool(BaseTool):
    """
    Launches a local application or file on the system.
    BUILD mode only.
    """
    def __init__(self):
        super().__init__(
            name="start_application",
            description="Launches a local application or opens a file/folder/URL using the OS default launcher. Requires BUILD mode.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The app name (e.g. 'notepad', 'calc'), folder path, file path, or URL to open."}
                },
                "required": ["path"]
            },
            required_mode=ExecutionMode.BUILD
        )

    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            if sys.platform == "win32":
                os.startfile(path)
                return f"Successfully requested OS to start: '{path}'"
            else:
                import subprocess
                if sys.platform == "darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
                return f"Successfully spawned process to open: '{path}'"
        except Exception as e:
            return f"Failed to start application '{path}': {str(e)}"

class ListProcessesTool(BaseTool):
    """
    Lists active processes on the host machine.
    PLAN and BUILD modes.
    """
    def __init__(self):
        super().__init__(
            name="list_processes",
            description="Lists active running processes on the system. Permitted in PLAN and BUILD modes.",
            parameters={
                "type": "object",
                "properties": {
                    "filter_name": {"type": "string", "description": "Optional substring to filter processes by name (case-insensitive)."}
                }
            },
            required_mode=ExecutionMode.PLAN
        )

    async def execute(self, filter_name: Optional[str] = None, **kwargs: Any) -> str:
        try:
            if sys.platform == "win32":
                cmd = ["tasklist"]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                output = stdout.decode("utf-8", errors="ignore")
            else:
                proc = await asyncio.create_subprocess_shell(
                    "ps -ax",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                output = stdout.decode("utf-8", errors="ignore")

            lines = output.splitlines()
            if not lines:
                return "No processes found."

            header = lines[0]
            result_lines = [header]

            if filter_name:
                f_lower = filter_name.lower()
                for line in lines[1:]:
                    if f_lower in line.lower():
                        result_lines.append(line)
                if len(result_lines) == 1:
                    return f"No processes matching filter '{filter_name}' were found."
            else:
                result_lines.extend(lines[1:50])
                if len(lines) > 50:
                    result_lines.append(f"... [truncated {len(lines) - 50} more processes]")

            return "\n".join(result_lines)
        except Exception as e:
            return f"Error listing processes: {str(e)}"

class KillProcessTool(BaseTool):
    """
    Terminates a process by name or PID.
    BUILD mode only.
    """
    def __init__(self):
        super().__init__(
            name="kill_process",
            description="Terminates a running process by name or process ID (PID). Requires BUILD mode.",
            parameters={
                "type": "object",
                "properties": {
                    "process_name": {"type": "string", "description": "Name of the process to kill (e.g., 'notepad.exe')."},
                    "pid": {"type": "integer", "description": "Process ID (PID) to kill."}
                }
            },
            required_mode=ExecutionMode.BUILD
        )

    async def execute(self, process_name: Optional[str] = None, pid: Optional[int] = None, **kwargs: Any) -> str:
        if not process_name and pid is None:
            return "Error: You must provide either process_name or pid."

        try:
            if sys.platform == "win32":
                if pid is not None:
                    cmd = ["taskkill", "/F", "/PID", str(pid)]
                else:
                    cmd = ["taskkill", "/F", "/IM", process_name]

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                out_str = stdout.decode("utf-8", errors="ignore") + stderr.decode("utf-8", errors="ignore")
                return f"Taskkill Output:\n{out_str.strip()}"
            else:
                if pid is not None:
                    cmd = f"kill -9 {pid}"
                else:
                    cmd = f"pkill -f {process_name}"

                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                out_str = stdout.decode("utf-8", errors="ignore") + stderr.decode("utf-8", errors="ignore")
                return f"Pkill Output:\n{out_str.strip() if out_str else 'Command executed.'}"
        except Exception as e:
            return f"Error killing process: {str(e)}"

class WebSearchTool(BaseTool):
    """
    Performs a DuckDuckGo HTML search.
    PLAN and BUILD modes.
    """
    def __init__(self):
        super().__init__(
            name="web_search",
            description="Performs a web search to retrieve real-time search result snippets. Allowed in PLAN and BUILD modes.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query to look up."}
                },
                "required": ["query"]
            },
            required_mode=ExecutionMode.PLAN
        )

    async def execute(self, query: str, **kwargs: Any) -> str:
        try:
            import httpx
            from urllib.parse import quote

            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                html = resp.text

            result_blocks = re.findall(
                r'<div class="result result--snippet.*?>(.*?)</div>\s*</div>\s*</div>',
                html,
                re.DOTALL
            )

            if not result_blocks:
                result_blocks = re.findall(
                    r'<td class="result-snippet.*?>(.*?)</td>',
                    html,
                    re.DOTALL
                )

            results = []
            for block in result_blocks[:5]:
                title_match = re.search(r'<a class="result__a" href="(.*?)">(.*?)</a>', block, re.DOTALL)
                snippet_match = re.search(r'<a class="result__snippet".*?>(.*?)</a>', block, re.DOTALL)

                if title_match and snippet_match:
                    raw_url = title_match.group(1)
                    import urllib.parse
                    parsed_url = raw_url
                    if "/l/?" in raw_url:
                        qs = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                        if "uddg" in qs:
                            parsed_url = qs["uddg"][0]

                    title = re.sub(r'<.*?>', '', title_match.group(2)).strip()
                    snippet = re.sub(r'<.*?>', '', snippet_match.group(1)).strip()
                    results.append(f"Title: {title}\nURL: {parsed_url}\nSnippet: {snippet}\n---")

            if not results:
                plain_text = re.sub(r'<script.*?>.*?</script>', '', html, flags=re.DOTALL)
                plain_text = re.sub(r'<style.*?>.*?</style>', '', plain_text, flags=re.DOTALL)
                plain_text = re.sub(r'<.*?>', ' ', plain_text)
                plain_text = re.sub(r'\s+', ' ', plain_text).strip()

                if "no results" in plain_text.lower():
                    return "No search results found."
                return f"Search content snippet:\n{plain_text[:2000]}..."

            return "\n".join(results)
        except Exception as e:
            return f"Error executing web search: {str(e)}"


