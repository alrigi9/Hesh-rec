@echo off
setlocal
cd /d "D:\claude word\plaud AI"
set PYTHONUTF8=1

echo ===================================================
echo   Live Meeting Copilot HUD Launcher
echo ===================================================

if exist "D:\claude word\plaud AI\.venv\Scripts\python.exe" (
    echo [*] Starting Copilot in Virtual Environment...
    "D:\claude word\plaud AI\.venv\Scripts\python.exe" -u "D:\claude word\plaud AI\live_copilot.py"
) else (
    echo [!] Virtual environment not found. Trying system python...
    python -u "D:\claude word\plaud AI\live_copilot.py"
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Process exited with code %ERRORLEVEL%
    pause
)
