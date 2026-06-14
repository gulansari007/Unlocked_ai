@echo off
title Unlocked AI Launcher ⚡
cd /d "%~dp0"

echo =======================================================
echo           ⚡ UNLOCKED AI TERMINAL CLIENT ⚡
echo =======================================================
echo.

:: Check if the server is already running on port 8000
netstat -ano | findstr :8000 >nul
if %errorlevel% equ 0 (
    echo [OK] Unlocked AI Core Server is already running.
) else (
    echo [STARTING] Unlocked AI server is not active.
    echo Spawning server in background window...
    :: Launch the FastAPI server in a minimized background cmd window
    start /min cmd /c "venv\Scripts\activate && unlocked start"
    echo Waiting 3 seconds for the server process to initialize...
    timeout /t 3 >nul
)

echo.
echo [LAUNCHING] Starting interactive chat client...
echo.

:: Activate virtual environment and start terminal chat
call venv\Scripts\activate
call unlocked chat

echo.
echo =======================================================
echo Unlocked AI session closed.
echo =======================================================
pause
