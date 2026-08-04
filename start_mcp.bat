@echo off
setlocal EnableExtensions
cd /d "%~dp0"

python bootstrap.py
if errorlevel 1 (
    echo ERROR: Failed to prepare the Local Repo MCP environment
    pause
    exit /b 1
)

echo [Local Repo MCP] Starting MCP Server...
".venv\Scripts\python.exe" launch_mcp.py
if errorlevel 1 pause
endlocal
