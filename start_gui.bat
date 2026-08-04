@echo off
setlocal EnableExtensions
cd /d "%~dp0"
python bootstrap.py
if errorlevel 1 (
  echo ERROR: Failed to prepare the Local Repo MCP environment
  pause
  exit /b 1
)
".venv\Scripts\python.exe" run_gui.py
if errorlevel 1 pause
endlocal
