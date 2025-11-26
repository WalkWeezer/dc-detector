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

# Используем docker-compose.prod.yml
if [ -f docker-compose.prod.yml ]; then
    echo "📋 Используется: docker-compose.prod.yml"
    docker compose -f docker-compose.prod.yml down --remove-orphans
else
    echo "⚠️  docker-compose.prod.yml не найден, пытаюсь остановить все контейнеры проекта..."
    docker ps -a --filter "name=dc-detector" --format "{{.ID}}" | xargs -r docker rm -f 2>/dev/null || true
fi
echo "✅ Docker контейнеры остановлены"

echo ""
echo "✨ Все сервисы остановлены"





