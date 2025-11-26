#!/bin/bash
# Единый скрипт деплоя для DC-Detector
# Поддерживает различные окружения (dev, prod, pi)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Параметры
ENV="${1:-prod}"
ACTION="${2:-deploy}"

usage() {
    echo "Использование: $0 [ENV] [ACTION]"
    echo ""
    echo "ENV (окружение):"
    echo "  prod  - Production (Raspberry Pi) - по умолчанию"
    echo "  dev   - Development"
    echo ""
    echo "ACTION (действие):"
    echo "  deploy   - Полный деплой (остановка + запуск) - по умолчанию"
    echo "  start    - Только запуск"
    echo "  stop     - Только остановка"
    echo "  restart  - Перезапуск"
    echo "  status   - Статус сервисов"
    echo "  logs     - Логи сервисов"
    echo ""
    echo "Примеры:"
    echo "  $0              # Production деплой"
    echo "  $0 prod deploy  # Production деплой (явно)"
    echo "  $0 dev start    # Development запуск"
    echo "  $0 prod restart # Production перезапуск"
}

cd "$PROJECT_ROOT"

# Загружаем compose-helper
source "$SCRIPT_DIR/compose-helper.sh"

case "$ACTION" in
    deploy)
        echo -e "${GREEN}🚀 Деплой DC-Detector ($ENV)${NC}"
        echo ""
        
        # Остановка существующих сервисов
        echo "🛑 Остановка существующих сервисов..."
        "$SCRIPT_DIR/stop-prod.sh" 2>/dev/null || true
        
        # Запуск сервисов
        echo ""
        echo "🚀 Запуск сервисов..."
        "$SCRIPT_DIR/start-prod.sh"
        ;;
        
    start)
        echo -e "${GREEN}▶️  Запуск DC-Detector ($ENV)${NC}"
        "$SCRIPT_DIR/start-prod.sh"
        ;;
        
    stop)
        echo -e "${RED}⏹️  Остановка DC-Detector ($ENV)${NC}"
        "$SCRIPT_DIR/stop-prod.sh"
        ;;
        
    restart)
        echo -e "${YELLOW}🔄 Перезапуск DC-Detector ($ENV)${NC}"
        "$SCRIPT_DIR/stop-prod.sh"
        sleep 2
        "$SCRIPT_DIR/start-prod.sh"
        ;;
        
    status)
        echo -e "${GREEN}📊 Статус DC-Detector ($ENV)${NC}"
        echo ""
        
        # Detection Service
        if [ -f .detection.pid ]; then
            PID=$(cat .detection.pid)
            if ps -p $PID > /dev/null 2>&1; then
                echo -e "✅ Detection Service: ${GREEN}запущен${NC} (PID: $PID)"
            else
                echo -e "⚠️  Detection Service: ${YELLOW}PID файл есть, но процесс не найден${NC}"
            fi
        else
            if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1; then
                PID=$(lsof -Pi :8001 -sTCP:LISTEN -t 2>/dev/null | head -1)
                echo -e "⚠️  Detection Service: ${YELLOW}запущен без PID файла${NC} (PID: $PID)"
            else
                echo -e "❌ Detection Service: ${RED}не запущен${NC}"
            fi
        fi
        
        # Docker сервисы
        echo ""
        echo "🐳 Docker сервисы:"
        COMPOSE_ARGS=$(get_compose_files "$PROJECT_ROOT")
        if [ -n "$COMPOSE_ARGS" ]; then
            docker compose $COMPOSE_ARGS ps
        else
            echo "⚠️  Compose файлы не найдены"
        fi
        
        # Проверка доступности
        echo ""
        echo "🔍 Проверка доступности:"
        check_service() {
            local url=$1
            local name=$2
            if curl -s --connect-timeout 2 "$url" >/dev/null 2>&1; then
                echo -e "  ✅ $name: ${GREEN}доступен${NC}"
            else
                echo -e "  ❌ $name: ${RED}недоступен${NC}"
            fi
        }
        
        check_service "http://localhost:8001/health" "Detection Service"
        check_service "http://localhost:8080/health" "Backend"
        check_service "http://localhost" "Frontend"
        ;;
        
    logs)
        echo -e "${GREEN}📋 Логи DC-Detector ($ENV)${NC}"
        echo ""
        
        # Логи Detection Service
        if [ -f .detection.log ]; then
            echo "📄 Detection Service (последние 50 строк):"
            tail -50 .detection.log
            echo ""
        fi
        
        # Логи Docker
        echo "🐳 Docker сервисы:"
        COMPOSE_ARGS=$(get_compose_files "$PROJECT_ROOT")
        if [ -n "$COMPOSE_ARGS" ]; then
            docker compose $COMPOSE_ARGS logs --tail=50 -f
        else
            echo "⚠️  Compose файлы не найдены"
        fi
        ;;
        
    *)
        echo -e "${RED}❌ Неизвестное действие: $ACTION${NC}"
        echo ""
        usage
        exit 1
        ;;
esac

