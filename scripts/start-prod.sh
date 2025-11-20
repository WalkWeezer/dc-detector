#!/bin/bash
# Скрипт запуска всей системы для продакшна на Raspberry Pi
# Оптимизированная версия с --system-site-packages

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 Запуск DC-Detector для продакшна (Raspberry Pi)"
echo ""

cd "$PROJECT_ROOT"

# Быстрая проверка системных зависимостей
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
check_command docker "Docker"
check_command "docker compose" "Docker Compose"

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

# ОПТИМИЗИРОВАННАЯ НАСТРОЙКА VENV С SYSTEM-SITE-PACKAGES
echo ""
echo "🐍 Настройка Python окружения..."

cd services/detection

# Создаем venv с доступом к системным пакетам если его нет
if [ ! -d "../../venv" ]; then
    echo "📦 Создаю виртуальное окружение с системными пакетами..."
    cd ../..
    python3 -m venv venv --system-site-packages
    cd services/detection
    echo "✅ Виртуальное окружение создано с --system-site-packages"
else
    echo "✅ Виртуальное окружение уже существует"
fi

# Активируем venv
source ../../venv/bin/activate

# Проверяем какие пакеты уже доступны из системы
echo "🔍 Проверка доступных системных пакетов..."
python -c "
import sys
print(f'Python путь: {sys.prefix}')
print(f'Системные пакеты доступны: {hasattr(sys, \"real_prefix\") or sys.base_prefix != sys.prefix}')
"

# Устанавливаем ТОЛЬКО недостающие пакеты
echo "📦 Установка недостающих пакетов..."

# Проверяем и устанавливаем только то, что действительно нужно
MISSING_PACKAGES=()

check_package() {
    local package=$1
    python -c "import $package" 2>/dev/null
    if [ $? -ne 0 ]; then
        MISSING_PACKAGES+=($package)
        echo "❌ $package - требуется установка"
    else
        echo "✅ $package - уже установлен"
    fi
}

echo ""
echo "🔍 Проверка ключевых пакетов:"
check_package flask
check_package cv2
check_package ultralytics
check_package numpy
check_package PIL

# Специальная проверка picamera2 (критично для Raspberry Pi)
echo ""
echo "📹 Проверка picamera2 (для Raspberry Pi камеры)..."
if python -c "import picamera2" 2>/dev/null; then
    echo "✅ picamera2 доступен в venv"
else
    echo "⚠️  picamera2 недоступен в venv"
    # Проверяем, доступен ли он системно
    if python3 -c "import picamera2" 2>/dev/null; then
        echo "   ℹ️  picamera2 доступен системно, но не в venv"
        echo "   💡 Возможно venv создан без --system-site-packages"
        
        # Проверяем, создан ли venv с --system-site-packages
        if [ -f "../../venv/pyvenv.cfg" ]; then
            if grep -q "include-system-site-packages = true" "../../venv/pyvenv.cfg"; then
                echo "   ⚠️  Venv создан с --system-site-packages, но picamera2 все равно недоступен"
                echo "   💡 Попробуйте пересоздать venv или установить picamera2 в venv"
            else
                echo "   ❌ Venv создан БЕЗ --system-site-packages"
                echo "   💡 Нужно пересоздать venv с --system-site-packages"
                echo ""
                read -p "Пересоздать venv с --system-site-packages? (y/n) " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    echo "🔄 Пересоздание venv..."
                    cd ../..
                    rm -rf venv
                    python3 -m venv venv --system-site-packages
                    cd services/detection
                    source ../../venv/bin/activate
                    echo "✅ Venv пересоздан с --system-site-packages"
                    # Проверяем снова
                    if python -c "import picamera2" 2>/dev/null; then
                        echo "✅ picamera2 теперь доступен в venv"
                    else
                        echo "⚠️  picamera2 все еще недоступен. Установите: sudo apt install python3-picamera2"
                    fi
                fi
            fi
        fi
    else
        echo "   ❌ picamera2 не установлен системно"
        echo "   💡 Установите: sudo apt install python3-picamera2"
    fi
fi

# Устанавливаем только недостающие пакеты
if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo ""
    echo "📥 Устанавливаю недостающие пакеты: ${MISSING_PACKAGES[*]}"
    pip install -q "${MISSING_PACKAGES[@]}"
    echo "✅ Недостающие пакеты установлены"
else
    echo ""
    echo "🎉 Все необходимые пакеты уже установлены!"
fi

cd "$PROJECT_ROOT"

# Остановка предыдущего процесса
if [ -f ".detection.pid" ]; then
    OLD_PID=$(cat .detection.pid)
    if kill -0 $OLD_PID 2>/dev/null; then
        echo "🛑 Останавливаю предыдущий Detection Service..."
        kill $OLD_PID
        sleep 2
    fi
    rm -f .detection.pid
fi

rm -f .detection.log

# ЗАПУСК DETECTION SERVICE
echo ""
echo "🎬 Запуск Detection Service..."

cd services/detection

# Запускаем напрямую с активированным venv
source ../../venv/bin/activate
nohup python detection_server.py > "../../.detection.log" 2>&1 &
DETECTION_PID=$!
echo "$DETECTION_PID" > "../../.detection.pid"
echo "✅ Detection Service запущен (PID: $DETECTION_PID)"

# Ждем инициализации
echo "⏳ Ожидание инициализации (12 секунд)..."
sleep 12

# Проверка работоспособности
echo "🔍 Проверка работоспособности..."
if curl -s --connect-timeout 5 http://localhost:8001/health >/dev/null; then
    echo "✅ Detection Service работает"
    
    # Проверка камеры
    if curl -s http://localhost:8001/api/detection | grep -q '"camera_available":true'; then
        echo "✅ Камера инициализирована"
    else
        echo "⚠️  Камера не инициализирована"
        echo "📋 Последние логи:"
        tail -f "../../.detection.log"
    fi
else
    echo "❌ Detection Service не отвечает"
    echo "📋 Логи:"
    tail -10 "../../.detection.log"
    echo "💡 Попробуйте запустить вручную:"
    echo "   cd services/detection && source ../../venv/bin/activate && python detection_server.py"
fi

cd "$PROJECT_ROOT"

# ЗАПУСК DOCKER СЕРВИСОВ
echo ""
echo "🐳 Запуск Backend и Frontend через Docker..."

if [ -f docker-compose.pi.yml ]; then
    docker compose -f docker-compose.yml -f docker-compose.pi.yml up -d --build
else
    docker compose up -d --build
fi

echo "⏳ Ожидание запуска Docker сервисов (8 секунд)..."
sleep 8

# ФИНАЛЬНАЯ ПРОВЕРКА
echo ""
echo "🔍 Финальная проверка сервисов..."

check_service() {
    if curl -s --connect-timeout 3 "$1" >/dev/null; then
        echo "✅ $2"
        return 0
    else
        echo "⚠️  $2"
        return 1
    fi
}

check_service "http://localhost:8001/health" "Detection Service"
check_service "http://localhost:8080/health" "Backend" 
check_service "http://localhost" "Frontend"

# ИТОГИ
echo ""
echo "============================================================"
echo "✨ Система запущена!"
echo "============================================================"
echo ""
echo "📍 Сервисы:"
echo "   • Frontend:  http://localhost"
echo "   • Backend:   http://localhost:8080" 
echo "   • Detection: http://localhost:8001"
echo ""
echo "📋 Полезные команды:"
echo "   • Логи Detection: tail -f .detection.log"
echo "   • Логи Docker:    docker compose logs -f"
echo "   • Остановка:      ./scripts/stop-prod.sh"
echo "   • Перезапуск:     ./scripts/stop-prod.sh && ./scripts/start-prod.sh"
echo ""