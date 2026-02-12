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
set "EMBED_DIR=%PROJECT_DIR%python_embed"
set "USE_EMBED=0"

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

:: Check if embedded python exists first (priority if previously downloaded)
if exist "%EMBED_DIR%\python.exe" (
    echo       Found Portable Python in %EMBED_DIR%
    set "PYTHON_CMD=%EMBED_DIR%\python.exe"
    set "USE_EMBED=1"
    goto :PYTHON_FOUND
)

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

:: --- If Python NOT found, Download Portable Version ---
if not defined PYTHON_CMD (
    echo [WARN] System Python not found. Installing Portable Python...
    
    if not exist "%EMBED_DIR%" mkdir "%EMBED_DIR%"
    
    REM Download Python Embeddable
    echo       Downloading Python 3.10.11 Embeddable...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip' -OutFile '%EMBED_DIR%\python.zip'"
    if !errorlevel! neq 0 ( exit /b 1 )
    
    REM Extract
    echo       Extracting Python...
    powershell -Command "Expand-Archive -Path '%EMBED_DIR%\python.zip' -DestinationPath '%EMBED_DIR%' -Force"
    del "%EMBED_DIR%\python.zip"
    
    REM Configure .pth file to import site (enable pip)
    echo       Configuring environment...
    (
        echo python310.zip
        echo .
        echo import site
    ) > "%EMBED_DIR%\python310._pth"
    
    REM Download get-pip.py
    echo       Downloading pip installer...
    powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%EMBED_DIR%\get-pip.py'"
    
    REM Install pip
    echo       Installing pip...
    "%EMBED_DIR%\python.exe" "%EMBED_DIR%\get-pip.py" --no-warn-script-location
    del "%EMBED_DIR%\get-pip.py"
    
    set "PYTHON_CMD=%EMBED_DIR%\python.exe"
    set "USE_EMBED=1"
    echo       Portable Python installed successfully.
)

:PYTHON_FOUND
echo.

:: --- Step 3: Setup Dependencies ---
echo [3/5] Setting up Dependencies...

if "%USE_EMBED%"=="1" goto :SETUP_EMBED
goto :SETUP_SYSTEM

:SETUP_EMBED
echo       Using Portable Python (skipping venv)...
    
REM Install requirements directly into portable python
echo       Installing Python dependencies...

"%PYTHON_CMD%" -m pip install -r "%PROJECT_DIR%requirements.txt" --quiet --no-warn-script-location 2>nul
if !errorlevel! neq 0 (
    echo       [WARN] Retrying minimal install...
    "%PYTHON_CMD%" -m pip install fastapi uvicorn pydantic numpy psutil python-multipart --quiet --no-warn-script-location 2>nul
)
goto :SETUP_DONE

:SETUP_SYSTEM
echo       Using System Python (creating venv)...

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo       Creating venv at %VENV_DIR%...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create venv. Check Python installation.
        pause
        exit /b 1
    )
)

REM Activate venv
call "%VENV_DIR%\Scripts\activate.bat"

REM Install dependencies
python -m pip install --upgrade pip --quiet 2>nul
echo       Installing Python dependencies...
pip install -r "%PROJECT_DIR%requirements.txt" --quiet 2>nul
if !errorlevel! neq 0 (
    echo       [WARN] Retrying minimal install...
    pip install fastapi uvicorn pydantic numpy psutil python-multipart --quiet 2>nul
)
goto :SETUP_DONE

:SETUP_DONE

:: Install test deps (common for both)
if "%USE_EMBED%"=="1" (
    "%PYTHON_CMD%" -m pip install pytest httpx --quiet --no-warn-script-location 2>nul
) else (
    pip install pytest httpx --quiet 2>nul
)

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

:: Start backend
if "%USE_EMBED%"=="1" (
    start "PipeStudio Backend (port %BACKEND_PORT%)" cmd /k "cd /d "%PROJECT_DIR%" && "%PYTHON_CMD%" -m uvicorn pipestudio.server:app --host 127.0.0.1 --port %BACKEND_PORT% --reload"
) else (
    start "PipeStudio Backend (port %BACKEND_PORT%)" cmd /k "cd /d "%PROJECT_DIR%" && call "%VENV_DIR%\Scripts\activate.bat" && python -m uvicorn pipestudio.server:app --host 127.0.0.1 --port %BACKEND_PORT% --reload"
)

:: Wait for backend
timeout /t 3 /nobreak >nul

:: Start frontend
start "PipeStudio Frontend (port %FRONTEND_PORT%)" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

:: Wait then open browser
timeout /t 3 /nobreak >nul
echo Opening browser...
start "" "http://localhost:%FRONTEND_PORT%"

echo.
echo PipeStudio is running! Close the backend/frontend windows to stop.
echo.
pause
