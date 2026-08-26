@echo off
title RecMap Desktop Recorder
cd /d "%~dp0"
echo ====================================================
echo   RecMap Desktop Recorder - Local Test Launcher
echo ====================================================
echo.
echo [1/2] Building latest source files...
call node build.js
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed with error code %errorlevel%
    goto end
)
echo.
echo [2/2] Launching Electron...
call node node_modules\electron\cli.js . --disable-gpu
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Electron exited with error code %errorlevel%
)

:end
echo.
echo ====================================================
pause
