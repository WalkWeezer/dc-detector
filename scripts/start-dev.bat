@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

rem Lightweight launcher that mirrors the manual steps:
rem  1. python services/detection/detection_server.py
rem  2. node services/backend/src/server.js
rem  3. npm run dev inside frontend

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_ROOT=%%~fI"
set "DETECTION_DIR=%PROJECT_ROOT%\services\detection"
set "BACKEND_DIR=%PROJECT_ROOT%\services\backend"
set "FRONTEND_DIR=%PROJECT_ROOT%\frontend"

echo.
echo [START] DC-Detector manual-style dev launcher
echo     Project root: %PROJECT_ROOT%
echo.

call :require_dir "%DETECTION_DIR%" || goto :error
call :require_dir "%BACKEND_DIR%" || goto :error
call :require_dir "%FRONTEND_DIR%" || goto :error
call :require_file "%DETECTION_DIR%" "detection_server.py" || goto :error
call :require_file "%BACKEND_DIR%" "src\server.js" || goto :error
call :require_file "%FRONTEND_DIR%" "package.json" || goto :error
call :require_command python || goto :error
call :require_command node || goto :error
call :require_command npm || goto :error

echo [RUN] Launching Detection Service (python detection_server.py)
call :start_service "Detection Service" "%DETECTION_DIR%" "python detection_server.py" || goto :error

echo [RUN] Launching Backend API (node src\server.js)
call :start_service "Backend API" "%BACKEND_DIR%" "node src\server.js" || goto :error

echo [RUN] Launching Frontend (npm run dev)
call :start_service "Frontend (Vite)" "%FRONTEND_DIR%" "npm run dev" || goto :error

echo.
echo ============================================================
echo [INFO] Services were started with the same commands, just like manual run.
echo     Detection: http://localhost:8001
echo     Backend:   http://localhost:8080
echo     Frontend:  http://localhost:5173
echo.
echo Stop them by closing the spawned windows or pressing CTRL+C in each.
echo Use INLINE_MODE=1 to keep everything in the current console.
echo ============================================================
echo.

if /I "%NO_PAUSE%"=="1" (
    goto :eof
) else (
    pause
    goto :eof
)

:error
echo.
echo [ERROR] Unable to start all services. See messages above.
if /I "%NO_PAUSE%"=="1" (
    exit /b 1
) else (
    pause
    exit /b 1
)

:require_dir
if not exist "%~1" (
    echo [ERROR] Directory not found: %~1
    exit /b 1
)
exit /b 0

:require_file
if not exist "%~1\%~2" (
    echo [ERROR] Required file %~2 not found in %~1
    exit /b 1
)
exit /b 0

:require_command
where %~1 >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Command not found in PATH: %~1
    exit /b 1
)
exit /b 0

:start_service
set "SERVICE_NAME=%~1"
set "SERVICE_DIR=%~2"
set "SERVICE_CMD=%~3"
if /I "%INLINE_MODE%"=="1" (
    start "" /b cmd /c "cd /d \"%SERVICE_DIR%\" && %SERVICE_CMD%"
) else (
    start "DC-Detector - %SERVICE_NAME%" cmd /k "cd /d \"%SERVICE_DIR%\" && %SERVICE_CMD%"
)
exit /b %errorlevel%
