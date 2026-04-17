@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "PYTHON="

if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" set "PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe"
if not defined PYTHON if exist "%SCRIPT_DIR%venv\Scripts\python.exe" set "PYTHON=%SCRIPT_DIR%venv\Scripts\python.exe"
if not defined PYTHON where py >nul 2>nul && set "PYTHON=py -3"
if not defined PYTHON where python >nul 2>nul && set "PYTHON=python"

if not defined PYTHON (
  >&2 echo error: no Python 3 interpreter found. Install Python 3.10+ or create a virtual environment.
  exit /b 1
)

%PYTHON% -m graphify %*
exit /b %errorlevel%
