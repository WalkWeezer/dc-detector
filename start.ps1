# Запуск системы детекции огня DC-Detector
# PowerShell скрипт для Windows

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DC-Detector - Запуск системы" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Проверка наличия Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[INFO] Python найден: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ОШИБКА] Python не найден! Установите Python 3.8+" -ForegroundColor Red
    Read-Host "Нажмите Enter для выхода"
    exit 1
}

Write-Host ""

# Получаем директорию скрипта
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Проверка наличия необходимых файлов
if (-not (Test-Path "camera-service\camera_server.py")) {
    Write-Host "[ОШИБКА] Файл camera-service\camera_server.py не найден!" -ForegroundColor Red
    Read-Host "Нажмите Enter для выхода"
    exit 1
}

if (-not (Test-Path "detection-service\detection_server.py")) {
    Write-Host "[ОШИБКА] Файл detection-service\detection_server.py не найден!" -ForegroundColor Red
    Read-Host "Нажмите Enter для выхода"
    exit 1
}

if (-not (Test-Path "bestfire.pt")) {
    Write-Host "[ПРЕДУПРЕЖДЕНИЕ] Файл bestfire.pt не найден в корне проекта!" -ForegroundColor Yellow
    Write-Host "[ПРЕДУПРЕЖДЕНИЕ] Detection Service может не работать" -ForegroundColor Yellow
    Write-Host ""
}

# Функция для очистки при выходе
function Cleanup {
    Write-Host ""
    Write-Host "[INFO] Остановка сервисов..." -ForegroundColor Yellow
    if ($CameraJob) { Stop-Job $CameraJob; Remove-Job $CameraJob }
    if ($DetectionJob) { Stop-Job $DetectionJob; Remove-Job $DetectionJob }
    Write-Host "[INFO] Сервисы остановлены" -ForegroundColor Green
}

# Перехватываем Ctrl+C
[Console]::TreatControlCAsInput = $false
Register-ObjectEvent -InputObject ([System.Console]) -EventName "CancelKeyPress" -Action {
    Cleanup
    exit
}

Write-Host "[INFO] Запуск Camera Service (порт 8000)..." -ForegroundColor Cyan
$CameraJob = Start-Job -ScriptBlock {
    Set-Location $using:ScriptDir\camera-service
    python camera_server.py
}

# Даем время camera-service запуститься
Start-Sleep -Seconds 3

Write-Host "[INFO] Запуск Detection Service (порт 8001)..." -ForegroundColor Cyan
$DetectionJob = Start-Job -ScriptBlock {
    Set-Location $using:ScriptDir\detection-service
    python detection_server.py
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Сервисы запущены!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Camera Service:    http://localhost:8000" -ForegroundColor Yellow
Write-Host "Detection Service: http://localhost:8001" -ForegroundColor Yellow
Write-Host ""
Write-Host "Для остановки нажмите Ctrl+C" -ForegroundColor Gray
Write-Host ""

# Мониторим статус джобов
try {
    while ($true) {
        Start-Sleep -Seconds 1
        if ($CameraJob.State -eq "Failed" -or $DetectionJob.State -eq "Failed") {
            Write-Host "[ОШИБКА] Один из сервисов завершился с ошибкой!" -ForegroundColor Red
            break
        }
    }
} finally {
    Cleanup
}

