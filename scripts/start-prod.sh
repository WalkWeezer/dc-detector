#!/bin/bash
# Скрипт запуска всей системы для продакшна на Raspberry Pi
# Запускает: Detection Service, Backend и Frontend через Docker

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 Запуск DC-Detector для продакшна (Raspberry Pi)"
echo ""

cd "$PROJECT_ROOT"

# Проверка зависимостей
echo "📋 Проверка зависимостей..."

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не найден. Установите: sudo apt install python3 python3-pip"
    exit 1
fi
echo "✅ Python 3: $(python3 --version)"

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не найден. Установите Docker:"
    echo "   curl -fsSL https://get.docker.com -o get-docker.sh"
    echo "   sudo sh get-docker.sh"
    exit 1
fi
echo "✅ Docker: $(docker --version)"

# Проверка Docker Compose
if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose не найден. Установите Docker Compose v2"
    exit 1
fi
echo "✅ Docker Compose: $(docker compose version)"

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
check_port 80 "Frontend (nginx)" || PORTS_OCCUPIED=1

if [ $PORTS_OCCUPIED -eq 1 ]; then
    echo ""
    echo "⚠️  Некоторые порты заняты. Остановите процессы или используйте другие порты."
    read -p "Продолжить? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Проверка .env файла
if [ ! -f .env ]; then
    echo ""
    echo "⚠️  Файл .env не найден. Создаю из env.example..."
    if [ -f env.example ]; then
        cp env.example .env
        echo "✅ Файл .env создан"
    else
        echo "❌ Файл env.example не найден"
        exit 1
    fi
fi

# Проверка DETECTION_URL в .env
if ! grep -q "DETECTION_URL" .env 2>/dev/null; then
    echo "⚠️  DETECTION_URL не найден в .env. Добавляю..."
    echo "DETECTION_URL=http://localhost:8001" >> .env
fi

# Создание необходимых директорий
echo ""
echo "📁 Создание директорий..."
mkdir -p data/detections/saved
mkdir -p services/detection/models
echo "✅ Директории созданы"

# Проверка зависимостей Detection Service
echo ""
echo "📦 Проверка зависимостей Detection Service..."

cd services/detection

# Проверка виртуального окружения
if [ ! -d "../../venv" ]; then
    echo "⚠️  Виртуальное окружение не найдено. Создаю..."
    cd ../..
    python3 -m venv venv
    cd services/detection
fi

# Активируем виртуальное окружение
source ../../venv/bin/activate

# Проверка Flask
if ! python -c "import flask" 2>/dev/null; then
    echo "⚠️  Flask не установлен. Устанавливаю..."
    pip install -q flask
fi
echo "✅ Flask установлен"

# Проверка других зависимостей
if ! python -c "import cv2" 2>/dev/null; then
    echo "⚠️  OpenCV не установлен. Устанавливаю..."
    pip install -q opencv-python-headless || {
        echo "⚠️  Не удалось установить через pip. Попробуйте: sudo apt install python3-opencv"
    }
fi

if ! python -c "from ultralytics import YOLO" 2>/dev/null; then
    echo "⚠️  Ultralytics не установлен. Устанавливаю..."
    pip install -q ultralytics || {
        echo "⚠️  Не удалось установить ultralytics"
    }
fi

cd "$PROJECT_ROOT"

# Запуск Detection Service в фоне
echo ""
echo "🎬 Запуск Detection Service..."
cd services/detection

# Проверка, не запущен ли уже
if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Detection Service уже запущен на порту 8001"
else
    # Активируем venv и используем полный путь к Python
    source ../../venv/bin/activate
    PYTHON_PATH=$(which python)
    
    # Запускаем в фоне с явным указанием рабочего каталога
    nohup "$PYTHON_PATH" detection_server.py > ../../.detection.log 2>&1 &
    DETECTION_PID=$!
    echo "$DETECTION_PID" > ../../.detection.pid
    echo "✅ Detection Service запущен (PID: $DETECTION_PID)"
    
    # Увеличиваем задержку для инициализации камеры
    echo "⏳ Ожидание инициализации камеры (5 секунд)..."
    sleep 5
    
    # Проверка работоспособности
    if curl -s http://localhost:8001/health >/dev/null 2>&1; then
        echo "✅ Detection Service работает"
        # Дополнительная проверка камеры
        CAMERA_STATUS=$(curl -s http://localhost:8001/api/detection 2>/dev/null | grep -o '"camera_available":[^,]*' || echo "")
        if echo "$CAMERA_STATUS" | grep -q "true"; then
            echo "✅ Камера инициализирована"
        else
            echo "⚠️  Камера не инициализирована. Проверьте логи: tail -f .detection.log"
        fi
    else
        echo "⚠️  Detection Service не отвечает, но процесс запущен"
        echo "💡 Проверьте логи: tail -f .detection.log"
    fi
fi

cd "$PROJECT_ROOT"

# Запуск Backend и Frontend через Docker
echo ""
echo "🎬 Запуск Backend и Frontend через Docker..."
echo "   (Это может занять некоторое время при первом запуске)"

# Используем продакшн compose файл
if [ -f docker-compose.pi.yml ]; then
    docker compose -f docker-compose.yml -f docker-compose.pi.yml up -d --build
else
    docker compose up -d --build
fi

# Ждем запуска
sleep 5

# Проверка работоспособности
echo ""
echo "🔍 Проверка работоспособности сервисов..."

check_service() {
    local url=$1
    local name=$2
    if curl -s "$url" >/dev/null 2>&1; then
        echo "✅ $name работает"
        return 0
    else
        echo "⚠️  $name не отвечает"
        return 1
    fi
}

check_service "http://localhost:8001/health" "Detection Service"
check_service "http://localhost:8080/health" "Backend"
check_service "http://localhost" "Frontend"

# Итоговая информация
echo ""
echo "============================================================"
echo "✨ Все сервисы запущены!"
echo "============================================================"
echo ""
echo "📍 Доступные сервисы:"
echo "   • Frontend (nginx):     http://localhost"
echo "   • Backend API:          http://localhost:8080"
echo "   • Detection Service:    http://localhost:8001"
echo ""
echo "📋 Полезные ссылки:"
echo "   • Health Check (Backend):     http://localhost:8080/health"
echo "   • Health Check (Detection):    http://localhost:8001/health"
echo "   • API Status:                 http://localhost:8080/api/detections/status"
echo "   • Video Stream:               http://localhost:8001/video_feed_raw"
echo ""
echo "🛑 Для остановки всех сервисов:"
echo "   Запустите: ./scripts/stop-prod.sh"
echo ""
echo "📝 Логи:"
echo "   • Detection Service: .detection.log"
echo "   • Docker контейнеры:  docker compose logs -f"
echo ""



