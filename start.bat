@echo off
setlocal enabledelayedexpansion
title PipeStudio Launcher
color 0A

echo ============================================
echo   PipeStudio v1.0 - Startup Script
echo ============================================
echo.

:: --- Configuration ---
set "PROJECT_DIR=%~dp0"
set "BACKEND_PORT=8500"
set "FRONTEND_PORT=5173"
set "VENV_DIR=%PROJECT_DIR%venv"
set "FRONTEND_DIR=%PROJECT_DIR%frontend"

:: --- Step 1: Kill existing processes on ports ---
echo [1/5] Killing processes on ports %BACKEND_PORT% and %FRONTEND_PORT%...

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%BACKEND_PORT% " ^| findstr "LISTENING" 2^>nul') do (
    if not "%%a"=="0" (
        echo       Killing PID %%a on port %BACKEND_PORT%
        taskkill /F /PID %%a >nul 2>&1
    )
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%FRONTEND_PORT% " ^| findstr "LISTENING" 2^>nul') do (
    if not "%%a"=="0" (
        echo       Killing PID %%a on port %FRONTEND_PORT%
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo       Ports cleared.
echo.

:: --- Step 2: Find Python ---
echo [2/5] Finding Python...

set "PYTHON_CMD="

:: Try py launcher with preferred versions
for %%v in (3.11 3.12 3.13 3.10 3.14) do (
    if not defined PYTHON_CMD (
        py -%%v --version >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_CMD=py -%%v"
            for /f "delims=" %%r in ('py -%%v --version 2^>^&1') do set "PY_VER=%%r"
            echo       Found: !PY_VER! ^(via py -%%v^)
        )
    )
)

:: Fallback: try plain python
if not defined PYTHON_CMD (
    python --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=python"
        for /f "delims=" %%r in ('python --version 2^>^&1') do set "PY_VER=%%r"
        echo       Found: !PY_VER! ^(via python^)
    )
)

if not defined PYTHON_CMD (
    echo [ERROR] Python not found! Install Python 3.10+ from https://python.org
    echo         Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo.

:: --- Step 3: Setup Python venv + dependencies ---
echo [3/5] Setting up Python virtual environment...

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo       Creating venv at %VENV_DIR%...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create venv. Check Python installation.
        pause
        exit /b 1
    )
    echo       venv created.
) else (
    echo       venv already exists.
)

:: Activate venv
call "%VENV_DIR%\Scripts\activate.bat"

:: Install/upgrade pip
python -m pip install --upgrade pip --quiet 2>nul

:: Install requirements
echo       Installing Python dependencies...
pip install -r "%PROJECT_DIR%requirements.txt" --quiet 2>nul
if !errorlevel! neq 0 (
    echo       [WARN] Some pip packages may have failed. Retrying without numba...
    pip install fastapi uvicorn pydantic numpy psutil --quiet 2>nul
)

:: Also install test deps
pip install pytest httpx --quiet 2>nul

echo       Python dependencies ready.
echo.

:: --- Step 4: Setup frontend ---
echo [4/5] Setting up frontend...

where node >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Node.js not found! Install from https://nodejs.org
    pause
    exit /b 1
)

for /f "delims=" %%r in ('node --version 2^>^&1') do echo       Node.js: %%r

if not exist "%FRONTEND_DIR%\node_modules" (
    echo       Installing npm dependencies...
    cd /d "%FRONTEND_DIR%"
    call npm install --silent 2>nul
    cd /d "%PROJECT_DIR%"
    echo       npm dependencies installed.
) else (
    echo       node_modules already exists.
)

echo.

:: --- Step 5: Launch services ---
echo [5/5] Starting PipeStudio...
echo.
echo       Backend:  http://localhost:%BACKEND_PORT%
echo       Frontend: http://localhost:%FRONTEND_PORT%
echo       API Docs: http://localhost:%BACKEND_PORT%/docs
echo.
echo ============================================
echo   Press Ctrl+C in either window to stop
echo ============================================
echo.

:: Start backend in a new window
start "PipeStudio Backend (port %BACKEND_PORT%)" cmd /k "cd /d "%PROJECT_DIR%" && call "%VENV_DIR%\Scripts\activate.bat" && python -m uvicorn pipestudio.server:app --host 127.0.0.1 --port %BACKEND_PORT% --reload"

:: Wait a moment for backend to start
timeout /t 3 /nobreak >nul

:: Start frontend in a new window
start "PipeStudio Frontend (port %FRONTEND_PORT%)" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

:: Wait a moment then open browser
timeout /t 3 /nobreak >nul

echo Opening browser...
start "" "http://localhost:%FRONTEND_PORT%"

echo.
echo PipeStudio is running! Close the backend/frontend windows to stop.
echo.
pause
