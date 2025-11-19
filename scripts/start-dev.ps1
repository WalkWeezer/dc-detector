# Скрипт запуска всей системы для разработки на Windows/ПК
# Запускает: Detection Service, Backend, Frontend (Vite)

$ErrorActionPreference = "Stop"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJECT_ROOT = Split-Path -Parent $SCRIPT_DIR

Write-Host "🚀 Запуск DC-Detector для разработки (Windows/ПК)" -ForegroundColor Cyan
Write-Host ""

# Переходим в корень проекта
Set-Location $PROJECT_ROOT

# Проверка зависимостей
Write-Host "📋 Проверка зависимостей..." -ForegroundColor Yellow

# Проверка Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python не найден. Установите Python 3.11+" -ForegroundColor Red
    exit 1
}

# Проверка Node.js
try {
    $nodeVersion = node --version
    Write-Host "✅ Node.js: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Node.js не найден. Установите Node.js 20+" -ForegroundColor Red
    exit 1
}

# Проверка портов
Write-Host "`n🔍 Проверка портов..." -ForegroundColor Yellow

$ports = @{
    8001 = "Detection Service"
    8080 = "Backend"
    5173 = "Frontend (Vite)"
}

$portsInUse = @()
foreach ($port in $ports.Keys) {
    $connection = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connection) {
        $portsInUse += $port
        Write-Host "⚠️  Порт $port ($($ports[$port])) уже занят!" -ForegroundColor Yellow
    } else {
        Write-Host "✅ Порт $port свободен" -ForegroundColor Green
    }
}

if ($portsInUse.Count -gt 0) {
    Write-Host "`n⚠️  Некоторые порты заняты. Остановите процессы или используйте другие порты." -ForegroundColor Yellow
    $continue = Read-Host "Продолжить? (y/n)"
    if ($continue -ne "y") {
        exit 1
    }
}

# Проверка зависимостей Detection Service
Write-Host "`n📦 Проверка зависимостей Detection Service..." -ForegroundColor Yellow
$detectionDir = Join-Path $PROJECT_ROOT "services\detection"
if (Test-Path $detectionDir) {
    Set-Location $detectionDir
    try {
        python -c "import flask" 2>$null
        Write-Host "✅ Flask установлен" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  Flask не установлен. Устанавливаю..." -ForegroundColor Yellow
        pip install -q flask
    }
} else {
    Write-Host "❌ Директория services\detection не найдена" -ForegroundColor Red
    exit 1
}

# Проверка зависимостей Backend
Write-Host "`n📦 Проверка зависимостей Backend..." -ForegroundColor Yellow
$backendDir = Join-Path $PROJECT_ROOT "services\backend"
if (Test-Path $backendDir) {
    Set-Location $backendDir
    if (-not (Test-Path "node_modules")) {
        Write-Host "⚠️  node_modules не найден. Устанавливаю зависимости..." -ForegroundColor Yellow
        npm install
    } else {
        Write-Host "✅ Зависимости Backend установлены" -ForegroundColor Green
    }
} else {
    Write-Host "❌ Директория services\backend не найдена" -ForegroundColor Red
    exit 1
}

# Проверка зависимостей Frontend
Write-Host "`n📦 Проверка зависимостей Frontend..." -ForegroundColor Yellow
$frontendDir = Join-Path $PROJECT_ROOT "frontend"
if (Test-Path $frontendDir) {
    Set-Location $frontendDir
    if (-not (Test-Path "node_modules")) {
        Write-Host "⚠️  node_modules не найден. Устанавливаю зависимости..." -ForegroundColor Yellow
        npm install
    } else {
        Write-Host "✅ Зависимости Frontend установлены" -ForegroundColor Green
    }
} else {
    Write-Host "❌ Директория frontend не найдена" -ForegroundColor Red
    exit 1
}

# Создание файла для хранения PID процессов
$pidsFile = Join-Path $PROJECT_ROOT ".dev-pids.txt"
if (Test-Path $pidsFile) {
    Remove-Item $pidsFile -Force
}

# Функция для запуска процесса в фоне
function Start-BackgroundProcess {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$Command,
        [string[]]$Arguments
    )
    
    $outputFile = Join-Path $PROJECT_ROOT ".$Name-output.log"
    $errorFile = Join-Path $PROJECT_ROOT ".$Name-error.log"
    
    # Запускаем процесс в фоне через Start-Process
    $process = Start-Process -FilePath $Command -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -PassThru -NoNewWindow -RedirectStandardOutput $outputFile -RedirectStandardError $errorFile
    
    # Сохраняем PID
    Add-Content -Path $pidsFile -Value "$Name=$($process.Id)"
    
    Write-Host "✅ $Name запущен (PID: $($process.Id))" -ForegroundColor Green
    return $process.Id
}

# Запуск Detection Service
Write-Host "`n🎬 Запуск Detection Service..." -ForegroundColor Cyan
Set-Location $detectionDir
$detectionPid = Start-BackgroundProcess -Name "detection" -WorkingDirectory $detectionDir -Command "python" -Arguments @("detection_server.py")
Start-Sleep -Seconds 2

# Проверка Detection Service
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8001/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
    Write-Host "✅ Detection Service работает" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Detection Service не отвечает, но процесс запущен" -ForegroundColor Yellow
}

# Запуск Backend
Write-Host "`n🎬 Запуск Backend..." -ForegroundColor Cyan
Set-Location $backendDir
$backendPid = Start-BackgroundProcess -Name "backend" -WorkingDirectory $backendDir -Command "node" -Arguments @("src\server.js")
Start-Sleep -Seconds 2

# Проверка Backend
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8080/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
    Write-Host "✅ Backend работает" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Backend не отвечает, но процесс запущен" -ForegroundColor Yellow
}

# Запуск Frontend (Vite)
Write-Host "`n🎬 Запуск Frontend (Vite)..." -ForegroundColor Cyan
Set-Location $frontendDir
# Для npm используем npx или прямой вызов через PowerShell
if (Get-Command npx -ErrorAction SilentlyContinue) {
    $frontendPid = Start-BackgroundProcess -Name "frontend" -WorkingDirectory $frontendDir -Command "npx" -Arguments @("vite")
} else {
    # Альтернатива через cmd
    $frontendPid = Start-BackgroundProcess -Name "frontend" -WorkingDirectory $frontendDir -Command "cmd" -Arguments @("/c", "npm run dev")
}
Start-Sleep -Seconds 3

# Итоговая информация
Write-Host "`n" -NoNewline
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "✨ Все сервисы запущены!" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""
Write-Host "📍 Доступные сервисы:" -ForegroundColor Yellow
Write-Host "   • Frontend (Vite):    http://localhost:5173" -ForegroundColor White
Write-Host "   • Backend API:        http://localhost:8080" -ForegroundColor White
Write-Host "   • Detection Service:  http://localhost:8001" -ForegroundColor White
Write-Host ""
Write-Host "📋 Полезные ссылки:" -ForegroundColor Yellow
Write-Host "   • Health Check (Backend):     http://localhost:8080/health" -ForegroundColor White
Write-Host "   • Health Check (Detection):   http://localhost:8001/health" -ForegroundColor White
Write-Host "   • API Status:                 http://localhost:8080/api/detections/status" -ForegroundColor White
Write-Host "   • Video Stream:               http://localhost:8001/video_feed_raw" -ForegroundColor White
Write-Host ""
Write-Host "🛑 Для остановки всех сервисов:" -ForegroundColor Yellow
Write-Host "   Запустите: .\scripts\stop-dev.ps1" -ForegroundColor White
Write-Host "   Или нажмите Ctrl+C и закройте это окно" -ForegroundColor White
Write-Host ""
Write-Host "📝 Логи процессов:" -ForegroundColor Yellow
Write-Host "   • Detection: .detection-output.log" -ForegroundColor White
Write-Host "   • Backend:   .backend-output.log" -ForegroundColor White
Write-Host "   • Frontend:  .frontend-output.log" -ForegroundColor White
Write-Host ""

# Ожидание завершения (Ctrl+C)
Write-Host "Нажмите Ctrl+C для остановки всех сервисов..." -ForegroundColor Gray
try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host "`n🛑 Остановка всех сервисов..." -ForegroundColor Yellow
    
    # Читаем PIDs из файла
    if (Test-Path $pidsFile) {
        $pids = Get-Content $pidsFile
        foreach ($line in $pids) {
            if ($line -match "(\w+)=(\d+)") {
                $name = $matches[1]
                $pid = [int]$matches[2]
                try {
                    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                    Write-Host "✅ Остановлен: $name (PID: $pid)" -ForegroundColor Green
                } catch {
                    Write-Host "⚠️  Не удалось остановить: $name (PID: $pid)" -ForegroundColor Yellow
                }
            }
        }
        Remove-Item $pidsFile -Force -ErrorAction SilentlyContinue
    }
    
    Write-Host "✨ Все сервисы остановлены" -ForegroundColor Green
}

