@echo off
REM Запуск системы детекции огня DC-Detector
REM Запускает camera-service и detection-service параллельно

echo ========================================
echo   DC-Detector - Запуск системы
echo ========================================
echo.

REM Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден! Установите Python 3.8+
    pause
    exit /b 1
)

echo [INFO] Python найден
echo.

REM Переходим в директорию проекта
cd /d "%~dp0"

REM Проверка наличия необходимых файлов
if not exist "camera-service\camera_server.py" (
    echo [ОШИБКА] Файл camera-service\camera_server.py не найден!
    pause
    exit /b 1
)

if not exist "detection-service\detection_server.py" (
    echo [ОШИБКА] Файл detection-service\detection_server.py не найден!
    pause
    exit /b 1
)

if not exist "bestfire.pt" (
    echo [ПРЕДУПРЕЖДЕНИЕ] Файл bestfire.pt не найден в корне проекта!
    echo [ПРЕДУПРЕЖДЕНИЕ] Detection Service может не работать
    echo.
)

echo [INFO] Запуск Camera Service (порт 8000)...
start "DC-Detector Camera Service" /D "%~dp0camera-service" python camera_server.py

REM Даем время camera-service запуститься
timeout /t 3 /nobreak >nul

echo [INFO] Запуск Detection Service (порт 8001)...
start "DC-Detector Detection Service" /D "%~dp0detection-service" python detection_server.py

echo.
echo ========================================
echo   Сервисы запущены!
echo ========================================
echo.
echo Camera Service:    http://localhost:8000
echo Detection Service: http://localhost:8001
echo.
echo Для остановки закройте оба окна или нажмите Ctrl+C в каждом
echo.
pause

