#!/bin/bash
# Скрипт запуска всей системы БЕЗ Docker для продакшна на Raspberry Pi
# Все сервисы запускаются напрямую, как в dev режиме

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 Запуск DC-Detector БЕЗ Docker (Raspberry Pi)"
echo ""

cd "$PROJECT_ROOT"

# Проверка системных зависимостей
echo "📋 Проверка системных зависимостей..."

check_command() {
    local cmd=$1
    local name=$2
    if command -v $cmd &> /dev/null; then
        echo "✅ $name"
        return 0
    else
        echo "❌ $name не найден"
        return 1
    fi
}

check_command python3 "Python 3"
check_command node "Node.js"
check_command npm "npm"

# Проверка портов
echo ""
echo "🔍 Проверка портов..."

check_port() {
    local port=$1
    local name=$2
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "⚠️  Порт $port ($name) уже занят!"
        return 1
    else
        echo "✅ Порт $port свободен"
        return 0
    fi
}

PORTS_OCCUPIED=0
check_port 8001 "Detection Service" || PORTS_OCCUPIED=1
check_port 8080 "Backend" || PORTS_OCCUPIED=1
check_port 5173 "Frontend (Vite)" || PORTS_OCCUPIED=1

if [ $PORTS_OCCUPIED -eq 1 ]; then
    echo ""
    echo "⚠️  Некоторые порты заняты."
    read -p "Продолжить? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Проверка .env
if [ ! -f .env ]; then
    echo "⚠️  Создаю .env..."
    cp env.example .env 2>/dev/null || echo "DETECTION_URL=http://localhost:8001" > .env
fi

# Создание директорий
mkdir -p data/detections/saved
mkdir -p services/detection/models

# Настройка Python окружения (аналогично start-prod.sh)
echo ""
echo "🐍 Настройка Python окружения..."

cd services/detection

if [ ! -d "../../venv" ]; then
    echo "📦 Создаю виртуальное окружение с системными пакетами..."
    cd ../..
    python3 -m venv venv --system-site-packages
    cd services/detection
fi

echo "🔌 Активация виртуального окружения..."
source ../../venv/bin/activate || {
    echo "❌ Ошибка активации venv"
    exit 1
}

# Проверка зависимостей Python
echo "📦 Проверка зависимостей Python..."
python -c "import flask, cv2, ultralytics, numpy, PIL" 2>/dev/null || {
    echo "⚠️  Некоторые пакеты отсутствуют, устанавливаю..."
    pip install -q flask opencv-python-headless numpy requests Pillow urllib3 Werkzeug ultralytics || {
        echo "❌ Ошибка установки зависимостей"
        exit 1
    }
}

cd "$PROJECT_ROOT"

# Остановка предыдущих процессов
echo ""
echo "🛑 Остановка предыдущих процессов..."

if [ -f ".detection.pid" ]; then
    OLD_PID=$(cat .detection.pid)
    if kill -0 $OLD_PID 2>/dev/null; then
        kill $OLD_PID 2>/dev/null || true
        sleep 1
    fi
    rm -f .detection.pid
fi

if [ -f ".backend.pid" ]; then
    OLD_PID=$(cat .backend.pid)
    if kill -0 $OLD_PID 2>/dev/null; then
        kill $OLD_PID 2>/dev/null || true
        sleep 1
    fi
    rm -f .backend.pid
fi

if [ -f ".frontend.pid" ]; then
    OLD_PID=$(cat .frontend.pid)
    if kill -0 $OLD_PID 2>/dev/null; then
        kill $OLD_PID 2>/dev/null || true
        sleep 1
    fi
    rm -f .frontend.pid
fi

# ЗАПУСК DETECTION SERVICE
echo ""
echo "🎬 Запуск Detection Service..."

cd services/detection
source ../../venv/bin/activate

nohup python detection_server.py > "../../.detection.log" 2>&1 &
DETECTION_PID=$!
echo "$DETECTION_PID" > "../../.detection.pid"
echo "✅ Detection Service запущен (PID: $DETECTION_PID)"

# Ждем инициализации
echo "⏳ Ожидание инициализации (12 секунд)..."
sleep 12

# Проверка Detection Service
if curl -s --connect-timeout 5 http://localhost:8001/health >/dev/null; then
    echo "✅ Detection Service работает"
else
    echo "⚠️  Detection Service не отвечает, но процесс запущен"
fi

cd "$PROJECT_ROOT"

# ЗАПУСК BACKEND
echo ""
echo "🎬 Запуск Backend..."

cd services/backend

# Проверка зависимостей
if [ ! -d "node_modules" ]; then
    echo "📦 Установка зависимостей Backend..."
    npm install --production --no-audit --no-fund || {
        echo "❌ Ошибка установки зависимостей"
        exit 1
    }
fi

# Убеждаемся, что DETECTION_URL правильный
export DETECTION_URL=${DETECTION_URL:-http://localhost:8001}
echo "   DETECTION_URL: $DETECTION_URL"

nohup node src/server.js > "../../.backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "../../.backend.pid"
echo "✅ Backend запущен (PID: $BACKEND_PID)"

# Ждем запуска
sleep 3

# Проверка Backend
if curl -s --connect-timeout 5 http://localhost:8080/health >/dev/null; then
    echo "✅ Backend работает"
else
    echo "⚠️  Backend не отвечает, но процесс запущен"
fi

cd "$PROJECT_ROOT"

# ЗАПУСК FRONTEND
echo ""
echo "🎬 Запуск Frontend (Vite)..."

cd frontend

# Проверка зависимостей
if [ ! -d "node_modules" ]; then
    echo "📦 Установка зависимостей Frontend..."
    npm install --no-audit --no-fund || {
        echo "❌ Ошибка установки зависимостей"
        exit 1
    }
fi

# Запуск Vite в production preview mode (или dev mode с --host)
nohup npm run dev -- --host --port 5173 > "../.frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "../.frontend.pid"
echo "✅ Frontend запущен (PID: $FRONTEND_PID)"

# Ждем запуска
sleep 5

# Проверка Frontend
if curl -s --connect-timeout 5 http://localhost:5173 >/dev/null; then
    echo "✅ Frontend работает"
else
    echo "⚠️  Frontend не отвечает, но процесс запущен"
fi

cd "$PROJECT_ROOT"

# ИТОГИ
echo ""
echo "============================================================"
echo "✨ Система запущена БЕЗ Docker!"
echo "============================================================"
echo ""
echo "📍 Сервисы:"
echo "   • Frontend:  http://localhost:5173"
echo "   • Backend:   http://localhost:8080" 
echo "   • Detection: http://localhost:8001"
echo ""
echo "📋 Полезные команды:"
echo "   • Логи Detection: tail -f .detection.log"
echo "   • Логи Backend:   tail -f .backend.log"
echo "   • Логи Frontend:  tail -f .frontend.log"
echo "   • Остановка:      ./scripts/stop-prod-direct.sh"
echo "   • Проверка PID:   cat .detection.pid .backend.pid .frontend.pid"
echo ""
echo "💡 Для доступа с других устройств используйте IP Raspberry Pi:"
echo "   http://$(hostname -I | awk '{print $1}'):5173"
echo ""

