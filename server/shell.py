import asyncio
import os
import sys
import uuid
import logging
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)

class PersistentShell:
    """
    Manages a single, persistent terminal shell process.
    Preserves environment variables, working directory, and execution context
    across sequential command invocations, behaving like a native terminal.
    """
    def __init__(self, initial_cwd: str):
        self.initial_cwd = os.path.abspath(initial_cwd)
        self.cwd = self.initial_cwd
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.lock = asyncio.Lock()
        self.is_windows = sys.platform == "win32"

    async def start(self) -> None:
        """Starts the persistent shell process."""
        if self.proc and self.proc.returncode is None:
            return

        if self.is_windows:
            cmd = "powershell.exe"
            args = ["-NoProfile", "-ExecutionPolicy", "Bypass"]
        else:
            cmd = "/bin/bash"
            # Fall back to sh if bash is not available
            if not os.path.exists(cmd):
                cmd = "sh"
            args = []

        logger.info(f"Starting persistent shell: {cmd} {' '.join(args)} in {self.cwd}")
        self.proc = await asyncio.create_subprocess_exec(
            cmd,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=self.cwd
        )

    async def stop(self) -> None:
        """Stops the persistent shell process."""
        if self.proc:
            try:
                self.proc.terminate()
                await self.proc.wait()
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None
            logger.info("Persistent shell stopped.")

    async def restart(self) -> None:
        """Restarts the shell process, preserving the last known directory."""
        await self.stop()
        await self.start()

    async def execute(self, command: str) -> AsyncGenerator[str, None]:
        """
        Executes a command in the persistent shell.
        Yields lines of stdout/stderr output in real-time.
        Updates internal current working directory (CWD) state upon completion.
        """
        async with self.lock:
            await self.start()
            if not self.proc or not self.proc.stdin or not self.proc.stdout:
                yield "Error: Failed to initialize persistent shell.\n"
                return

            sentinel = f"__CMD_DONE_{uuid.uuid4().hex}__"
            
            # Prepare commands to run: user command, get new CWD, then output the sentinel
            if self.is_windows:
                # Use Out-String to avoid truncation and output raw text
                cwd_cmd = "$PWD.Path"
                sentinel_cmd = f"Write-Output '{sentinel}'"
                full_payload = f"{command}\n\n{cwd_cmd}\n{sentinel_cmd}\n"
            else:
                cwd_cmd = "pwd"
                sentinel_cmd = f"echo '{sentinel}'"
                full_payload = f"{command}\n\n{cwd_cmd}\n{sentinel_cmd}\n"

            # Write the payload to the stdin of the subprocess
            try:
                self.proc.stdin.write(full_payload.encode("utf-8"))
                await self.proc.stdin.drain()
            except Exception as e:
                yield f"Error writing to shell stdin: {str(e)}\n"
                await self.restart()
                return
            # Read the output stream line-by-line
            pending_line = None
            while True:
                try:
                    line_bytes = await self.proc.stdout.readline()
                    if not line_bytes:
                        # Process terminated unexpectedly
                        yield "Shell process terminated unexpectedly.\n"
                        await self.restart()
                        break
                    
                    line = line_bytes.decode("utf-8", errors="ignore")
                    
                    # If we hit the sentinel, the command is done
                    if sentinel in line:
                        break
                        
                    if pending_line is not None:
                        yield pending_line
                    
                    pending_line = line
                except Exception as e:
                    yield f"Error reading from shell stdout: {str(e)}\n"
                    await self.restart()
                    break

            # At this point, pending_line holds the line before the sentinel, which is the CWD path.
            if pending_line is not None:
                potential_cwd = pending_line.strip()
                if os.path.isdir(potential_cwd):
                    self.cwd = potential_cwd
                    logger.info(f"Shell working directory updated to: {self.cwd}")
                else:
                    # Not a directory, yield it as normal command output
                    yield pending_line
