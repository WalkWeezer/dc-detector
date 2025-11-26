#!/bin/bash
# Скрипт остановки всех сервисов для продакшна на Raspberry Pi

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🛑 Остановка всех сервисов..."

cd "$PROJECT_ROOT"

# Остановка Detection Service
if [ -f .detection.pid ]; then
    DETECTION_PID=$(cat .detection.pid)
    if ps -p $DETECTION_PID > /dev/null 2>&1; then
        echo "🛑 Остановка Detection Service (PID: $DETECTION_PID)..."
        kill $DETECTION_PID 2>/dev/null || true
        sleep 1
        # Принудительная остановка если не остановился
        if ps -p $DETECTION_PID > /dev/null 2>&1; then
            kill -9 $DETECTION_PID 2>/dev/null || true
        fi
        echo "✅ Detection Service остановлен"
    else
        echo "⚠️  Detection Service уже не запущен"
    fi
    rm -f .detection.pid
else
    # Пытаемся найти процесс по порту
    if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1; then
        PID=$(lsof -Pi :8001 -sTCP:LISTEN -t 2>/dev/null | head -1)
        if [ ! -z "$PID" ]; then
            echo "🛑 Остановка Detection Service (PID: $PID)..."
            kill $PID 2>/dev/null || true
            sleep 1
            if ps -p $PID > /dev/null 2>&1; then
                kill -9 $PID 2>/dev/null || true
            fi
            echo "✅ Detection Service остановлен"
        fi
    fi
fi

# Остановка Docker контейнеров
echo "🛑 Остановка Docker контейнеров..."
if [ -f docker-compose.pi-standalone.yml ]; then
    # Используем standalone файл для Raspberry Pi (избегает конфликта network_mode/networks)
    docker compose -f docker-compose.pi-standalone.yml down
elif [ -f docker-compose.pi.yml ]; then
    # Fallback на объединение файлов (может вызвать конфликт network_mode/networks)
    docker compose -f docker-compose.yml -f docker-compose.pi.yml down
else
    docker compose down
fi
echo "✅ Docker контейнеры остановлены"

echo ""
echo "✨ Все сервисы остановлены"





