@echo off
title Unlocked AI  ⚡
chcp 65001 >nul
cd /d "%~dp0"

:: Enable ANSI color support
reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>&1

cls

:: ─── BOOT BANNER ──────────────────────────────────────────────────────────────
echo.
echo  [38;5;135m ██╗   ██╗███╗   ██╗██╗      ██████╗  ██████╗██╗  ██╗███████╗██████╗ [0m
echo  [38;5;135m ██║   ██║████╗  ██║██║     ██╔═══██╗██╔════╝██║ ██╔╝██╔════╝██╔══██╗[0m
echo  [38;5;141m ██║   ██║██╔██╗ ██║██║     ██║   ██║██║     █████╔╝ █████╗  ██║  ██║[0m
echo  [38;5;39m ██║   ██║██║╚██╗██║██║     ██║   ██║██║     ██╔═██╗ ██╔══╝  ██║  ██║[0m
echo  [38;5;39m ╚██████╔╝██║ ╚████║███████╗╚██████╔╝╚██████╗██║  ██╗███████╗██████╔╝[0m
echo  [38;5;45m  ╚═════╝ ╚═╝  ╚═══╝╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝╚═════╝ [0m
echo.
echo  [38;5;245m              ◈  A I   A G E N T I C   F R A M E W O R K  ◈[0m
echo.
echo  [38;5;93m ───────────────────────────────────────────────────────────────────────[0m
echo.

:: ─── VENV SETUP ───────────────────────────────────────────────────────────────
if not exist venv (
    echo  [38;5;220m ⟳  First Launch Detected — Initializing Environment...[0m
    echo.
    python -m venv venv
    if %errorlevel% neq 0 (
        echo  [38;5;196m ✗  Failed to create virtual environment.[0m
        echo  [38;5;245m    Please ensure Python 3.10+ is installed and on your PATH.[0m
        echo.
        pause
        exit /b %errorlevel%
    )

    echo  [38;5;220m ⟳  Installing Unlocked AI dependencies...[0m
    call venv\Scripts\activate
    python -m pip install --upgrade pip --quiet
    pip install -e . --quiet
    if %errorlevel% neq 0 (
        echo  [38;5;196m ✗  Dependency installation failed.[0m
        echo.
        pause
        exit /b %errorlevel%
    )
    echo  [38;5;82m ✓  Installation complete![0m
    echo.
) else (
    call venv\Scripts\activate
)

:: ─── FIRST-RUN ONBOARDING ─────────────────────────────────────────────────────
if not exist .env (
    echo  [38;5;220m ◆  First-Time Setup — Starting Configuration Wizard...[0m
    echo  [38;5;245m    This will only run once. You can reconfigure with: unlocked onboard[0m
    echo.
    call unlocked onboard
    echo.
    echo  [38;5;82m ✓  Configuration saved![0m
    echo.
)

:: ─── SERVER CHECK ─────────────────────────────────────────────────────────────
echo  [38;5;245m ◈  Checking server status...[0m
netstat -ano | findstr :8000 >nul
if %errorlevel% equ 0 (
    echo  [38;5;82m ✓  Unlocked AI Server is already running on port 8000[0m
) else (
    echo  [38;5;220m ⟳  Starting Unlocked AI Server in background...[0m
    start /min cmd /c "venv\Scripts\activate && unlocked start"
    timeout /t 4 >nul
    echo  [38;5;82m ✓  Server started![0m
)

echo.
echo  [38;5;93m ───────────────────────────────────────────────────────────────────────[0m
echo  [38;5;135m  Launching interactive chat — type /help to see commands[0m
echo  [38;5;93m ───────────────────────────────────────────────────────────────────────[0m
echo.

:: ─── LAUNCH CHAT ──────────────────────────────────────────────────────────────
call unlocked chat

:: ─── EXIT SCREEN ──────────────────────────────────────────────────────────────
echo.
echo  [38;5;93m ───────────────────────────────────────────────────────────────────────[0m
echo  [38;5;135m  Session closed. Thank you for using Unlocked AI! 👋[0m
echo  [38;5;93m ───────────────────────────────────────────────────────────────────────[0m
echo.
pause
