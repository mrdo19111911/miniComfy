@echo off
title PipeStudio - Stop
color 0C

echo ============================================
echo   PipeStudio - Stopping Services
echo ============================================
echo.

set "BACKEND_PORT=8500"
set "FRONTEND_PORT=5173"

echo Killing processes on port %BACKEND_PORT% (backend)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%BACKEND_PORT% " ^| findstr "LISTENING" 2^>nul') do (
    if not "%%a"=="0" (
        echo   Killing PID %%a
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo Killing processes on port %FRONTEND_PORT% (frontend)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%FRONTEND_PORT% " ^| findstr "LISTENING" 2^>nul') do (
    if not "%%a"=="0" (
        echo   Killing PID %%a
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo.
echo All PipeStudio processes stopped.
pause
