@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [Local Repo MCP] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create venv. Install Python 3.11+
        pause
        exit /b 1
    )
    call ".venv\Scripts\pip.exe" install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo [Local Repo MCP] Starting MCP Server...
".venv\Scripts\python.exe" server.py
if errorlevel 1 pause
endlocal
