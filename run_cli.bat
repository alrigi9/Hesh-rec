@echo off
setlocal enabledelayedexpansion

title Plaud AI Meeting Studio CLI
cd /d "%~dp0"

echo ===============================================================================
echo                     🎙️  PLAUD AI MEETING STUDIO LAUNCHER                       
echo ===============================================================================
echo.

:: 1. Check Virtual Environment
if not exist ".venv\Scripts\activate.bat" (
    echo [!] Virtual environment not detected. Creating .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [X] Failed to create virtual environment. Ensure Python is installed and added to PATH.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
    echo [*] Installing dependencies from requirements.txt...
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

:: 2. Check if .env exists
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [*] Created .env from .env.example template.
    )
)

:: 3. Run meeting_cli.py with provided arguments or interactive mode
if "%~1"=="" (
    python meeting_cli.py
) else (
    python meeting_cli.py %*
)

if errorlevel 1 (
    echo.
    echo [!] Process exited with code %errorlevel%.
    pause
)

endlocal
