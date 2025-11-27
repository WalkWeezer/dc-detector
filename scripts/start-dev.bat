@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM Безопасная инициализация переменных для Windows
set "ERROR_OCCURRED=0"

REM Универсальный старт для разработки на Windows/Wsl2
REM Запускает Detection Service, Backend, Frontend (Vite)

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

echo.
echo [START] Запуск DC-Detector для разработки (Windows/Wsl2)
echo.

REM Переходим в корень проекта
cd /d "%PROJECT_ROOT%"

REM Проверяем окружение
echo [CHECK] Проверяем окружение...
echo.

REM Проверяем Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не найден. Установите Python 3.11+
    echo.
    echo Нажмите любую клавишу для выхода...
    pause >nul
    exit /b 1
) else (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo [OK] Python: %%i
)

REM Проверяем Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js не найден. Установите Node.js 20+
    echo.
    echo Нажмите любую клавишу для выхода...
    pause >nul
    exit /b 1
) else (
    for /f "tokens=*" %%i in ('node --version') do echo [OK] Node.js: %%i
)

REM Проверяем порты
echo.
echo [CHECK] Проверяем состояние портов...
echo.

set PORTS_IN_USE=0
netstat -an | findstr ":8001" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Порт 8001 (Detection Service) занят
    set PORTS_IN_USE=1
) else (
    echo [OK] Порт 8001 свободен
)

netstat -an | findstr ":8080" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Порт 8080 (Backend) занят
    set PORTS_IN_USE=1
) else (
    echo [OK] Порт 8080 свободен
)

netstat -an | findstr ":5173" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Порт 5173 (Frontend) занят
    set PORTS_IN_USE=1
) else (
    echo [OK] Порт 5173 свободен
)

if !PORTS_IN_USE!==1 (
    echo.
    echo [WARNING] Некоторые порты заняты. Остановите процессы или измените порты.
    set /p CONTINUE="Продолжить запуск? (y/n): "
    if /i not "!CONTINUE!"=="y" (
        echo.
        echo Нажмите любую клавишу для выхода...
        pause >nul
        exit /b 1
    )
)

REM Проверяем зависимости Detection Service
echo.
echo [CHECK] Проверяем зависимости Detection Service...
set "DETECTION_DIR=%PROJECT_ROOT%\services\detection"
if not exist "%DETECTION_DIR%" (
    echo [ERROR] Каталог services\detection не найден
    echo.
    echo Нажмите любую клавишу для выхода...
    pause >nul
    exit /b 1
)

cd /d "%DETECTION_DIR%"
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Flask не установлен. Устанавливаем...
    pip install -q flask
) else (
    echo [OK] Flask установлен
)

REM Проверяем зависимости Backend
echo.
echo [CHECK] Проверяем зависимости Backend...
set "BACKEND_DIR=%PROJECT_ROOT%\services\backend"
if not exist "%BACKEND_DIR%" (
    echo [ERROR] Каталог services\backend не найден
    echo.
    echo Нажмите любую клавишу для выхода...
    pause >nul
    exit /b 1
)

cd /d "%BACKEND_DIR%"
if not exist "node_modules" (
    echo [WARN] node_modules отсутствует. Устанавливаем зависимости...
    call npm install
) else (
    echo [OK] Зависимости Backend установлены
)

REM Проверяем зависимости Frontend
echo.
echo [CHECK] Проверяем зависимости Frontend...
set "FRONTEND_DIR=%PROJECT_ROOT%\frontend"
if not exist "%FRONTEND_DIR%" (
    echo [ERROR] Каталог frontend не найден
    echo.
    echo Нажмите любую клавишу для выхода...
    pause >nul
    exit /b 1
)

cd /d "%FRONTEND_DIR%"
if not exist "node_modules" (
    echo [WARN] node_modules отсутствует. Устанавливаем зависимости...
    call npm install
) else (
    echo [OK] Зависимости Frontend установлены
)

REM Создаём файл для хранения PID процессов
set "PIDS_FILE=%PROJECT_ROOT%\.dev-pids.txt"
if exist "%PIDS_FILE%" del /f /q "%PIDS_FILE%"

REM Запускаем Detection Service
echo.
echo [START] Запускаем Detection Service...
cd /d "%DETECTION_DIR%"
if not exist "detection_server.py" (
    echo [ERROR] Файл detection_server.py не найден в %DETECTION_DIR%
    echo.
    echo Нажмите любую клавишу для выхода...
    pause >nul
    exit /b 1
)
start "DC-Detector Detection Service" /min cmd /c "python detection_server.py > %PROJECT_ROOT%\.detection-output.log 2>&1"
timeout /t 2 /nobreak >nul

REM Проверяем Detection Service
powershell -NoProfile -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:8001/health' -UseBasicParsing -TimeoutSec 2; Write-Host 'OK Detection Service работает' -ForegroundColor Green } catch { Write-Host 'WARNING Detection Service не отвечает, проверьте логи' -ForegroundColor Yellow }" 2>nul
if errorlevel 1 (
    echo WARNING Detection Service не отвечает, проверьте логи
)

REM Запускаем Backend
echo.
echo [START] Запускаем Backend...
cd /d "%BACKEND_DIR%"
if not exist "src\server.js" (
    echo [ERROR] Файл src\server.js не найден в %BACKEND_DIR%
    echo.
    echo Нажмите любую клавишу для выхода...
    pause >nul
    exit /b 1
)
start "DC-Detector Backend" /min cmd /c "node src\server.js > %PROJECT_ROOT%\.backend-output.log 2>&1"
timeout /t 2 /nobreak >nul

REM Проверяем Backend
powershell -NoProfile -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:8080/health' -UseBasicParsing -TimeoutSec 2; Write-Host 'OK Backend работает' -ForegroundColor Green } catch { Write-Host 'WARNING Backend не отвечает, проверьте логи' -ForegroundColor Yellow }" 2>nul
if errorlevel 1 (
    echo WARNING Backend не отвечает, проверьте логи
)

REM Запускаем Frontend (Vite)
echo.
echo [START] Запускаем Frontend (Vite)...
cd /d "%FRONTEND_DIR%"
if not exist "package.json" (
    echo [ERROR] Файл package.json не найден в %FRONTEND_DIR%
    echo.
    echo Нажмите любую клавишу для выхода...
    pause >nul
    exit /b 1
)
start "DC-Detector Frontend" /min cmd /c "npx vite > %PROJECT_ROOT%\.frontend-output.log 2>&1"
timeout /t 3 /nobreak >nul

REM Результаты запуска
echo.
echo ============================================================
echo [SUCCESS] Все сервисы запущены!
echo ============================================================
echo.
echo [INFO] Точки входа:
echo    - Frontend (Vite):    http://localhost:5173
echo    - Backend API:        http://localhost:8080
echo    - Detection Service:  http://localhost:8001
echo.
echo [INFO] Полезные ссылки:
echo    - Health Check (Backend):     http://localhost:8080/health
echo    - Health Check (Detection):   http://localhost:8001/health
echo    - API Status:                 http://localhost:8080/api/detections/status
echo    - Video Stream:               http://localhost:8001/video_feed_raw
echo.
echo [STOP] Чтобы остановить все процессы:
echo    Выполните: .\scripts\stop-dev.bat
echo.
echo [LOGS] Логи сервисов:
echo    - Detection: .detection-output.log
echo    - Backend:   .backend-output.log
echo    - Frontend:  .frontend-output.log
echo.
echo Все процессы запущены в отдельных окнах.
echo.
echo [WARNING] Внимание: не закрывайте это окно! Для корректной остановки используйте stop-dev.bat.
echo.
echo Нажмите любую клавишу для завершения (окна сервисов останутся открыты)...
timeout /t 2 /nobreak >nul
pause

