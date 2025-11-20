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

# Проверка и установка зависимостей
echo "🔧 Проверка и установка Python зависимостей..."

REQUIREMENTS_FILE="requirements.txt"
if [ -f "$REQUIREMENTS_FILE" ]; then
    echo "📦 Установка зависимостей из $REQUIREMENTS_FILE..."
    pip install -q -r "$REQUIREMENTS_FILE"
else
    echo "📦 Установка основных зависимостей..."
    pip install -q flask opencv-python-headless ultralytics
fi

# Проверяем установку ключевых библиотек
echo "🔍 Проверка установленных библиотек..."
python -c "import flask; print('✅ Flask установлен')" || echo "❌ Flask не установлен"
python -c "import cv2; print('✅ OpenCV установлен')" || echo "❌ OpenCV не установлен"
python -c "from ultralytics import YOLO; print('✅ Ultralytics установлен')" || echo "❌ Ultralytics не установлен"

cd "$PROJECT_ROOT"

# Остановка предыдущего процесса если запущен
if [ -f ".detection.pid" ]; then
    OLD_PID=$(cat .detection.pid)
    if kill -0 $OLD_PID 2>/dev/null; then
        echo "🛑 Останавливаю предыдущий Detection Service (PID: $OLD_PID)..."
        kill $OLD_PID
        sleep 3
    fi
    rm -f .detection.pid
fi

rm -f .detection.log

# Запуск Detection Service в фоне с правильной активацией venv
echo ""
echo "🎬 Запуск Detection Service..."
cd services/detection

# Сохраняем абсолютные пути
DETECTION_DIR=$(pwd)
PROJECT_ROOT=$(cd ../.. && pwd)
VENV_PATH="$PROJECT_ROOT/venv"

# Создаем скрипт для запуска с правильным окружением
LAUNCH_SCRIPT="$PROJECT_ROOT/launch_detection.sh"

cat > "$LAUNCH_SCRIPT" << EOF
#!/bin/bash
cd "$DETECTION_DIR"
source "$VENV_PATH/bin/activate"
export PYTHONPATH="$DETECTION_DIR:$PYTHONPATH"
exec python detection_server.py
EOF

chmod +x "$LAUNCH_SCRIPT"

echo "📁 Рабочий каталог: $DETECTION_DIR"
echo "🐍 Виртуальное окружение: $VENV_PATH"

# Запускаем через launch скрипт чтобы гарантировать активацию venv
nohup "$LAUNCH_SCRIPT" > "$PROJECT_ROOT/.detection.log" 2>&1 &
DETECTION_PID=$!
echo "$DETECTION_PID" > "$PROJECT_ROOT/.detection.pid"
echo "✅ Detection Service запущен (PID: $DETECTION_PID)"

# Даем больше времени для инициализации камеры
echo "⏳ Ожидание инициализации Detection Service (15 секунд)..."
sleep 15

# Проверка работоспособности с повторными попытками
echo "🔍 Проверка работоспособности Detection Service..."

MAX_RETRIES=6
RETRY_COUNT=0
DETECTION_READY=false
CAMERA_READY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    echo "Попытка $((RETRY_COUNT + 1))/$MAX_RETRIES..."
    
    # Проверяем health endpoint
    if curl -s --connect-timeout 10 http://localhost:8001/health >/dev/null 2>&1; then
        echo "✅ Detection Service отвечает на health check"
        
        # Проверяем статус камеры через API
        API_RESPONSE=$(curl -s --connect-timeout 10 http://localhost:8001/api/detection 2>/dev/null || echo "{}")
        if echo "$API_RESPONSE" | grep -q '"camera_available":true'; then
            echo "✅ Камера успешно инициализирована"
            CAMERA_READY=true
            DETECTION_READY=true
            break
        elif echo "$API_RESPONSE" | grep -q '"camera_available":false'; then
            echo "❌ Камера не инициализирована (camera_available: false)"
            echo "💡 Проверьте доступность камеры в системе"
        else
            echo "⚠️  Не удалось получить статус камеры из API"
        fi
    else
        echo "⏳ Detection Service не отвечает на health check"
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
        echo "Ожидание 5 секунд перед следующей попыткой..."
        sleep 5
    fi
done

# Проверяем логи если камера не инициализирована
if [ "$CAMERA_READY" = false ]; then
    echo ""
    echo "⚠️  Проблема с инициализацией камеры"
    echo "🔍 Проверка доступности камеры в системе..."
    
    # Проверяем доступные камеры
    if ls /dev/video* >/dev/null 2>&1; then
        echo "📹 Доступные видео устройства:"
        ls /dev/video*
    else
        echo "❌ Видео устройства не найдены в /dev/video*"
    fi
    
    # Проверяем процессы использующие камеру
    echo "🔍 Процессы использующие камеру:"
    lsof /dev/video* 2>/dev/null || echo "Не удалось получить информацию о процессах"
    
    echo ""
    echo "📋 Последние логи Detection Service:"
    tail -20 "$PROJECT_ROOT/.detection.log"
    
    echo ""
    echo "💡 Возможные решения:"
    echo "   1. Проверьте подключение камеры к Raspberry Pi"
    echo "   2. Убедитесь что камера включена в raspi-config"
    echo "   3. Попробуйте перезагрузить систему"
    echo "   4. Проверьте права доступа к /dev/video*"
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

# Ждем запуска контейнеров
echo "⏳ Ожидание запуска Docker контейнеров (15 секунд)..."
sleep 15

# Проверка работоспособности всех сервисов
echo ""
echo "🔍 Проверка работоспособности всех сервисов..."

check_service() {
    local url=$1
    local name=$2
    local max_retries=$3
    local retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if curl -s --connect-timeout 10 "$url" >/dev/null 2>&1; then
            echo "✅ $name работает"
            return 0
        else
            retry_count=$((retry_count + 1))
            if [ $retry_count -lt $max_retries ]; then
                echo "⏳ $name не отвечает, повторная попытка $retry_count/$max_retries..."
                sleep 5
            fi
        fi
    done
    
    echo "⚠️  $name не отвечает после $max_retries попыток"
    return 1
}

check_service "http://localhost:8001/health" "Detection Service" 3
check_service "http://localhost:8080/health" "Backend" 3
check_service "http://localhost" "Frontend" 3

# Проверка видео потока если камера инициализирована
if [ "$CAMERA_READY" = true ]; then
    echo ""
    echo "🎥 Проверка видео потока..."
    
    if curl -s --connect-timeout 10 http://localhost:8001/video_feed_raw >/dev/null 2>&1; then
        echo "✅ Видео поток доступен"
    else
        echo "⚠️  Видео поток не доступен"
    fi
else
    echo ""
    echo "⚠️  Видео поток недоступен - камера не инициализирована"
fi

# Итоговая информация
echo ""
echo "============================================================"
if [ "$CAMERA_READY" = true ]; then
    echo "✨ Все сервисы запущены! Камера работает."
else
    echo "⚠️  Сервисы запущены, но камера не инициализирована"
fi
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
echo "   • Detection API:              http://localhost:8001/api/detection"
echo ""
echo "🛑 Для остановки всех сервисов:"
echo "   Запустите: ./scripts/stop-prod.sh"
echo ""
echo "📝 Логи:"
echo "   • Detection Service: tail -f .detection.log"
echo "   • Docker контейнеры:  docker compose logs -f"
echo "   • Конкретный контейнер: docker compose logs -f backend"
echo ""

# Удаляем временный скрипт
rm -f "$LAUNCH_SCRIPT"