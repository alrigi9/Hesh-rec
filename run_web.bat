@echo off
setlocal enabledelayedexpansion

title Plaud AI Web Studio (HTML5)
cd /d "%~dp0"

echo ===============================================================================
echo                   🎙️  PLAUD AI WEB STUDIO (HTML5 DASHBOARD)                    
echo ===============================================================================
echo.
echo [*] Starting Local Web Server on http://localhost:8080...
echo [*] Serving directory: src/meetingcli/web/
echo.

start http://localhost:8080

python -m http.server 8080 --directory src/meetingcli/web

endlocal
