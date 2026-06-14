@echo off
title Unlocked AI Launcher ⚡
cd /d "%~dp0"

echo =======================================================
echo           ⚡ UNLOCKED AI LAUNCHER ⚡
echo =======================================================
echo.

:: 1. Check if virtual environment exists. If not, create and install packages.
if not exist venv (
    echo [FIRST LAUNCH] Setting up Python Virtual Environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create Python virtual environment.
        echo Please ensure Python 3.10+ is installed and added to your system PATH.
        pause
        exit /b %errorlevel%
    )
    
    echo [INSTALLING] Activating environment and installing Unlocked AI dependencies...
    call venv\Scripts\activate
    python -m pip install --upgrade pip
    pip install -e .
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install Unlocked AI package dependencies.
        pause
        exit /b %errorlevel%
    )
    echo [OK] Installation successfully completed!
    echo.
) else (
    :: Activate existing virtual environment
    call venv\Scripts\activate
)

:: 2. Check if configuration (.env) exists. If not, trigger onboarding wizard.
if not exist .env (
    echo [SETUP REQUIRED] Starting onboarding configuration wizard...
    echo.
    call unlocked onboard
    echo.
    echo Setup complete! Starting application...
    echo.
)

:: 3. Check if the backend server is already running on port 8000
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

:: Start terminal chat
call unlocked chat

echo.
echo =======================================================
echo Unlocked AI session closed.
echo =======================================================
pause
