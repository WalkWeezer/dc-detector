@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
goto :main

:wait_for_service
setlocal EnableDelayedExpansion
set "SERVICE_NAME=%~1"
set "SERVICE_URL=%~2"
set "MAX_RETRIES=%~3"
set "RETRY_DELAY=%~4"
if not defined SERVICE_NAME set "SERVICE_NAME=Service"
if not defined SERVICE_URL set "SERVICE_URL=http://localhost"
if not defined MAX_RETRIES set "MAX_RETRIES=10"
if not defined RETRY_DELAY set "RETRY_DELAY=2"
set /a ATTEMPT=1
:wait_for_service_loop
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%SERVICE_URL%' -UseBasicParsing -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    if !ATTEMPT! geq !MAX_RETRIES! (
        echo [WARNING] %SERVICE_NAME% is not responding after !MAX_RETRIES! attempts, check logs.
        endlocal & exit /b 1
    )
    timeout /t !RETRY_DELAY! /nobreak >nul
    set /a ATTEMPT+=1
    goto :wait_for_service_loop
) else (
    echo [OK] %SERVICE_NAME% is responding
    endlocal & exit /b 0
)

:main

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

echo.
echo [START] Starting DC-Detector development environment
echo.

cd /d "%PROJECT_ROOT%"
if errorlevel 1 (
    echo [ERROR] Failed to change to project root: %PROJECT_ROOT%
    echo.
    echo Press any key to exit...
    pause
    if errorlevel 1 pause
    goto :error_exit
)

echo [CHECK] Checking environment...
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+
    echo.
    echo Press any key to exit...
    pause
    if errorlevel 1 pause
    goto :error_exit
) else (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo [OK] Python: %%i
)

node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install Node.js 20+
    echo.
    echo Press any key to exit...
    pause
    if errorlevel 1 pause
    goto :error_exit
) else (
    for /f "tokens=*" %%i in ('node --version') do echo [OK] Node.js: %%i
)

echo.
echo [CHECK] Checking ports...
echo.

set PORTS_IN_USE=0
netstat -an | findstr ":8001" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Port 8001 ^(Detection Service^) is in use
    set PORTS_IN_USE=1
) else (
    echo [OK] Port 8001 is free
)

netstat -an | findstr ":8080" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Port 8080 ^(Backend^) is in use
    set PORTS_IN_USE=1
) else (
    echo [OK] Port 8080 is free
)

netstat -an | findstr ":5173" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Port 5173 ^(Frontend^) is in use
    set PORTS_IN_USE=1
) else (
    echo [OK] Port 5173 is free
)

if !PORTS_IN_USE!==1 (
    echo.
    echo [WARNING] Some ports are in use. Stop processes or change ports.
    set /p CONTINUE="Continue? (y/n): "
    if /i not "!CONTINUE!"=="y" (
        echo.
        echo Press any key to exit...
        pause
        if errorlevel 1 pause
        goto :error_exit
    )
)

echo.
echo [CHECK] Checking Detection Service dependencies...
set "DETECTION_DIR=%PROJECT_ROOT%\services\detection"
if not exist "%DETECTION_DIR%" (
    echo [ERROR] Directory services\detection not found
    echo.
    echo Press any key to exit...
    pause
    if errorlevel 1 pause
    goto :error_exit
)

cd /d "%DETECTION_DIR%"
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Flask not installed. Installing...
    pip install -q flask
) else (
    echo [OK] Flask is installed
)

echo.
echo [CHECK] Checking Backend dependencies...
set "BACKEND_DIR=%PROJECT_ROOT%\services\backend"
if not exist "%BACKEND_DIR%" (
    echo [ERROR] Directory services\backend not found
    echo.
    echo Press any key to exit...
    pause
    if errorlevel 1 pause
    goto :error_exit
)

cd /d "%BACKEND_DIR%"
if not exist "node_modules" (
    echo [WARN] node_modules missing. Installing dependencies...
    call npm install
) else (
    echo [OK] Backend dependencies installed
)

echo.
echo [CHECK] Checking Frontend dependencies...
set "FRONTEND_DIR=%PROJECT_ROOT%\frontend"
if not exist "%FRONTEND_DIR%" (
    echo [ERROR] Directory frontend not found
    echo.
    echo Press any key to exit...
    pause
    if errorlevel 1 pause
    goto :error_exit
)

cd /d "%FRONTEND_DIR%"
if not exist "node_modules" (
    echo [WARN] node_modules missing. Installing dependencies...
    call npm install
) else (
    echo [OK] Frontend dependencies installed
)

set "PIDS_FILE=%PROJECT_ROOT%\.dev-pids.txt"
if exist "%PIDS_FILE%" del /f /q "%PIDS_FILE%"

echo.
echo [START] Starting Detection Service...
cd /d "%DETECTION_DIR%"
if not exist "detection_server.py" (
    echo [ERROR] File detection_server.py not found in %DETECTION_DIR%
    echo.
    echo Press any key to exit...
    pause
    if errorlevel 1 pause
    goto :error_exit
)
start "DC-Detector Detection Service" /min cmd /c "cd /d \"%DETECTION_DIR%\" && python detection_server.py > \"%PROJECT_ROOT%\.detection-output.log\" 2>&1"
if errorlevel 1 (
    echo [ERROR] Failed to start Detection Service
    echo Check logs: %PROJECT_ROOT%\.detection-output.log
    echo.
    echo Press any key to exit...
    pause
    if errorlevel 1 pause
    goto :error_exit
)
timeout /t 3 /nobreak >nul
call :wait_for_service "Detection service" "http://localhost:8001/health" 15 3
if errorlevel 1 (
    echo [WARNING] Detection service still not responding, check logs: .detection-output.log
)

echo.
echo [START] Starting Backend...
cd /d "%BACKEND_DIR%"
if not exist "src\server.js" (
    echo [ERROR] File src\server.js not found in %BACKEND_DIR%
    echo.
    echo Press any key to exit...
    pause
    if errorlevel 1 pause
    goto :error_exit
)
start "DC-Detector Backend" /min cmd /c "cd /d \"%BACKEND_DIR%\" && node src\server.js > \"%PROJECT_ROOT%\.backend-output.log\" 2>&1"
if errorlevel 1 (
    echo [ERROR] Failed to start Backend
    echo Check logs: %PROJECT_ROOT%\.backend-output.log
    echo.
    echo Press any key to exit...
    pause
    if errorlevel 1 pause
    goto :error_exit
)
timeout /t 3 /nobreak >nul
call :wait_for_service "Backend API" "http://localhost:8080/health" 10 2
if errorlevel 1 (
    echo [WARNING] Backend API still not responding, check logs: .backend-output.log
)

echo.
echo [START] Starting Frontend (Vite)...
cd /d "%FRONTEND_DIR%"
if not exist "package.json" (
    echo [ERROR] File package.json not found in %FRONTEND_DIR%
    echo.
    echo Press any key to exit...
    pause
    if errorlevel 1 pause
    goto :error_exit
)
start "DC-Detector Frontend" /min cmd /c "cd /d \"%FRONTEND_DIR%\" && npx vite > \"%PROJECT_ROOT%\.frontend-output.log\" 2>&1"
if errorlevel 1 (
    echo [ERROR] Failed to start Frontend
    echo Check logs: %PROJECT_ROOT%\.frontend-output.log
    echo.
    echo Press any key to exit...
    pause
    if errorlevel 1 pause
    goto :error_exit
)
timeout /t 4 /nobreak >nul
call :wait_for_service "Frontend dev server" "http://localhost:5173" 10 2
if errorlevel 1 (
    echo [WARNING] Frontend dev server still not responding, check logs: .frontend-output.log
)

echo.
echo ============================================================
echo [SUCCESS] All services started!
echo ============================================================
echo.
echo [INFO] Entry points:
echo    - Frontend (Vite):    http://localhost:5173
echo    - Backend API:        http://localhost:8080
echo    - Detection Service:  http://localhost:8001
echo.
echo [INFO] Useful links:
echo    - Health Check (Backend):     http://localhost:8080/health
echo    - Health Check (Detection):   http://localhost:8001/health
echo    - API Status:                 http://localhost:8080/api/detections/status
echo    - Video Stream:               http://localhost:8001/video_feed_raw
echo.
echo [STOP] To stop all processes:
echo    Run: .\scripts\stop-dev.bat
echo.
echo [LOGS] Service logs:
echo    - Detection: .detection-output.log
echo    - Backend:   .backend-output.log
echo    - Frontend:  .frontend-output.log
echo.
echo All processes are running in separate windows.
echo.
echo [WARNING] Do not close this window^! Use stop-dev.bat to stop services.
echo.
echo ============================================================
echo Press any key to finish (service windows will remain open)...
echo ============================================================
echo.
pause
if errorlevel 1 pause
exit /b 0

:error_exit
echo.
echo ============================================================
echo [ERROR] Script execution failed
echo ============================================================
echo.
echo Check error messages above.
echo.
echo Press any key to exit (window will stay open)...
pause
if errorlevel 1 pause
echo.
echo Window will stay open. Type 'exit' to close.
cmd /k
exit /b 1
