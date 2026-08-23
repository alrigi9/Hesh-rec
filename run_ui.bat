@echo off
setlocal enabledelayedexpansion

title Plaud AI Meeting Studio Web UI
cd /d "%~dp0"

echo ===============================================================================
echo                   🎙️  PLAUD AI MEETING STUDIO - WEB UI LAUNCHER                 
echo ===============================================================================
echo.

:: 1. Check Virtual Environment
if not exist ".venv\Scripts\activate.bat" (
    echo [!] Virtual environment not detected. Creating .venv...
    python -m venv .venv
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
        echo [*] Created .env from template.
    )
)

echo [*] Starting Plaud AI Streamlit Web Studio on http://localhost:8501...
echo [*] Press Ctrl+C in this window to stop the server.
echo.

streamlit run app.py --server.port=8501 --server.headless=false

if errorlevel 1 (
    echo.
    echo [!] Streamlit exited with error code %errorlevel%.
    pause
)

endlocal
