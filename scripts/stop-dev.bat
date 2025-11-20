@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM Скрипт остановки всех сервисов для разработки на Windows/ПК

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "PIDS_FILE=%PROJECT_ROOT%\.dev-pids.txt"

echo.
echo 🛑 Остановка всех сервисов...
echo.

cd /d "%PROJECT_ROOT%"

REM Останавливаем процессы по именам окон
echo Остановка процессов по именам окон...
taskkill /FI "WINDOWTITLE eq DC-Detector Detection Service*" /T /F >nul 2>&1
if not errorlevel 1 echo ✅ Остановлен Detection Service

taskkill /FI "WINDOWTITLE eq DC-Detector Backend*" /T /F >nul 2>&1
if not errorlevel 1 echo ✅ Остановлен Backend

taskkill /FI "WINDOWTITLE eq DC-Detector Frontend*" /T /F >nul 2>&1
if not errorlevel 1 echo ✅ Остановлен Frontend

REM Останавливаем процессы по портам
echo.
echo Остановка процессов по портам...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8001" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
    if not errorlevel 1 echo ✅ Остановлен процесс на порту 8001 (PID: %%a)
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
    if not errorlevel 1 echo ✅ Остановлен процесс на порту 8080 (PID: %%a)
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
    if not errorlevel 1 echo ✅ Остановлен процесс на порту 5173 (PID: %%a)
)


REM Удаляем файл с PIDs
if exist "%PIDS_FILE%" (
    del /f /q "%PIDS_FILE%" >nul 2>&1
    echo.
    echo ✅ Файл .dev-pids.txt удален
)

echo.
echo ✨ Готово!
echo.
echo Нажмите любую клавишу для выхода...
pause >nul

