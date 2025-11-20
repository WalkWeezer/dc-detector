@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM Скрипт запуска всей системы для разработки на Windows/ПК
REM Запускает: Detection Service, Backend, Frontend (Vite)

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

echo.
echo 🚀 Запуск DC-Detector для разработки (Windows/ПК)
echo.

REM Переходим в корень проекта
cd /d "%PROJECT_ROOT%"

REM Проверка зависимостей
echo 📋 Проверка зависимостей...
echo.

REM Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден. Установите Python 3.11+
    pause
    exit /b 1
) else (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo ✅ Python: %%i
)

REM Проверка Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js не найден. Установите Node.js 20+
    pause
    exit /b 1
) else (
    for /f "tokens=*" %%i in ('node --version') do echo ✅ Node.js: %%i
)

REM Проверка портов
echo.
echo 🔍 Проверка портов...
echo.

set PORTS_IN_USE=0
netstat -an | findstr ":8001" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Port 8001 Detection Service - BUSY
    set PORTS_IN_USE=1
) else (
    echo [OK] Port 8001 - FREE
)

netstat -an | findstr ":8080" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Port 8080 Backend - BUSY
    set PORTS_IN_USE=1
) else (
    echo [OK] Port 8080 - FREE
)

netstat -an | findstr ":5173" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Port 5173 Frontend - BUSY
    set PORTS_IN_USE=1
) else (
    echo [OK] Port 5173 - FREE
)

if !PORTS_IN_USE!==1 (
    echo.
    echo [WARNING] Some ports are busy. Stop processes or use different ports.
    set /p CONTINUE="Continue? (y/n): "
    if /i not "!CONTINUE!"=="y" (
        pause
        exit /b 1
    )
)

REM Проверка зависимостей Detection Service
echo.
echo 📦 Проверка зависимостей Detection Service...
set "DETECTION_DIR=%PROJECT_ROOT%\services\detection"
if not exist "%DETECTION_DIR%" (
    echo ❌ Директория services\detection не найдена
    pause
    exit /b 1
)

cd /d "%DETECTION_DIR%"
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Flask не установлен. Устанавливаю...
    pip install -q flask
) else (
    echo ✅ Flask установлен
)

REM Проверка зависимостей Backend
echo.
echo 📦 Проверка зависимостей Backend...
set "BACKEND_DIR=%PROJECT_ROOT%\services\backend"
if not exist "%BACKEND_DIR%" (
    echo ❌ Директория services\backend не найдена
    pause
    exit /b 1
)

cd /d "%BACKEND_DIR%"
if not exist "node_modules" (
    echo ⚠️  node_modules не найден. Устанавливаю зависимости...
    call npm install
) else (
    echo ✅ Зависимости Backend установлены
)

REM Проверка зависимостей Frontend
echo.
echo 📦 Проверка зависимостей Frontend...
set "FRONTEND_DIR=%PROJECT_ROOT%\frontend"
if not exist "%FRONTEND_DIR%" (
    echo ❌ Директория frontend не найдена
    pause
    exit /b 1
)

cd /d "%FRONTEND_DIR%"
if not exist "node_modules" (
    echo ⚠️  node_modules не найден. Устанавливаю зависимости...
    call npm install
) else (
    echo ✅ Зависимости Frontend установлены
)

REM Создание файла для хранения PID процессов
set "PIDS_FILE=%PROJECT_ROOT%\.dev-pids.txt"
if exist "%PIDS_FILE%" del /f /q "%PIDS_FILE%"

REM Запуск Detection Service
echo.
echo 🎬 Запуск Detection Service...
cd /d "%DETECTION_DIR%"
if not exist "detection_server.py" (
    echo ❌ Файл detection_server.py не найден в %DETECTION_DIR%
    pause
    exit /b 1
)
start "DC-Detector Detection Service" /min cmd /c "python detection_server.py > %PROJECT_ROOT%\.detection-output.log 2> %PROJECT_ROOT%\.detection-error.log"
timeout /t 2 /nobreak >nul

REM Проверка Detection Service
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:8001/health' -UseBasicParsing -TimeoutSec 2; Write-Host '✅ Detection Service работает' -ForegroundColor Green } catch { Write-Host '⚠️  Detection Service не отвечает, но процесс запущен' -ForegroundColor Yellow }" 2>nul
if errorlevel 1 (
    echo ⚠️  Detection Service не отвечает, но процесс запущен
)

REM Запуск Backend
echo.
echo 🎬 Запуск Backend...
cd /d "%BACKEND_DIR%"
if not exist "src\server.js" (
    echo ❌ Файл src\server.js не найден в %BACKEND_DIR%
    pause
    exit /b 1
)
start "DC-Detector Backend" /min cmd /c "node src\server.js > %PROJECT_ROOT%\.backend-output.log 2> %PROJECT_ROOT%\.backend-error.log"
timeout /t 2 /nobreak >nul

REM Проверка Backend
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:8080/health' -UseBasicParsing -TimeoutSec 2; Write-Host '✅ Backend работает' -ForegroundColor Green } catch { Write-Host '⚠️  Backend не отвечает, но процесс запущен' -ForegroundColor Yellow }" 2>nul
if errorlevel 1 (
    echo ⚠️  Backend не отвечает, но процесс запущен
)

REM Запуск Frontend (Vite)
echo.
echo 🎬 Запуск Frontend (Vite)...
cd /d "%FRONTEND_DIR%"
if not exist "package.json" (
    echo ❌ Файл package.json не найден в %FRONTEND_DIR%
    pause
    exit /b 1
)
start "DC-Detector Frontend" /min cmd /c "npx vite > %PROJECT_ROOT%\.frontend-output.log 2> %PROJECT_ROOT%\.frontend-error.log"
timeout /t 3 /nobreak >nul

REM Итоговая информация
echo.
echo ============================================================
echo ✨ Все сервисы запущены!
echo ============================================================
echo.
echo 📍 Доступные сервисы:
echo    • Frontend (Vite):    http://localhost:5173
echo    • Backend API:        http://localhost:8080
echo    • Detection Service:  http://localhost:8001
echo.
echo 📋 Полезные ссылки:
echo    • Health Check (Backend):     http://localhost:8080/health
echo    • Health Check (Detection):   http://localhost:8001/health
echo    • API Status:                 http://localhost:8080/api/detections/status
echo    • Video Stream:               http://localhost:8001/video_feed_raw
echo.
echo 🛑 Для остановки всех сервисов:
echo    Запустите: .\scripts\stop-dev.bat
echo.
echo 📝 Логи процессов:
echo    • Detection: .detection-output.log
echo    • Backend:   .backend-output.log
echo    • Frontend:  .frontend-output.log
echo.
echo Окна сервисов запущены в свернутом виде.
echo.
echo ⚠️  ВАЖНО: Не закрывайте это окно! Оно контролирует запущенные сервисы.
echo    Для остановки всех сервисов запустите: .\scripts\stop-dev.bat
echo    Или закройте это окно (сервисы продолжат работать в фоне)
echo.
echo.
echo Нажмите любую клавишу для выхода (сервисы продолжат работать)...
pause

