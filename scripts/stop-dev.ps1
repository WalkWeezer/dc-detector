# Скрипт остановки всех сервисов для разработки на Windows/ПК

$ErrorActionPreference = "Stop"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJECT_ROOT = Split-Path -Parent $SCRIPT_DIR
$pidsFile = Join-Path $PROJECT_ROOT ".dev-pids.txt"

Write-Host "🛑 Остановка всех сервисов..." -ForegroundColor Yellow

if (-not (Test-Path $pidsFile)) {
    Write-Host "⚠️  Файл с PID процессов не найден. Останавливаю процессы по портам..." -ForegroundColor Yellow
    
    # Останавливаем процессы по портам
    $ports = @(8001, 8080, 5173)
    foreach ($port in $ports) {
        $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        foreach ($conn in $connections) {
            try {
                Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
                Write-Host "✅ Остановлен процесс на порту $port (PID: $($conn.OwningProcess))" -ForegroundColor Green
            } catch {
                Write-Host "⚠️  Не удалось остановить процесс на порту $port" -ForegroundColor Yellow
            }
        }
    }
} else {
    $pids = Get-Content $pidsFile
    foreach ($line in $pids) {
        if ($line -match "(\w+)=(\d+)") {
            $name = $matches[1]
            $pid = [int]$matches[2]
            try {
                $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
                if ($process) {
                    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                    Write-Host "✅ Остановлен: $name (PID: $pid)" -ForegroundColor Green
                } else {
                    Write-Host "⚠️  Процесс $name (PID: $pid) уже не запущен" -ForegroundColor Yellow
                }
            } catch {
                Write-Host "⚠️  Не удалось остановить: $name (PID: $pid)" -ForegroundColor Yellow
            }
        }
    }
    Remove-Item $pidsFile -Force -ErrorAction SilentlyContinue
}

Write-Host "✨ Готово!" -ForegroundColor Green


