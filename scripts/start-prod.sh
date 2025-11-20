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
    VENV_NEEDS_RECREATE=false
else
    echo "✅ Виртуальное окружение уже существует"
    # Проверяем, создан ли venv с --system-site-packages
    if [ -f "../../venv/pyvenv.cfg" ]; then
        if ! grep -q "include-system-site-packages = true" "../../venv/pyvenv.cfg"; then
            echo "⚠️  Venv создан БЕЗ --system-site-packages"
            echo "💡 Для работы с picamera2 нужно пересоздать venv"
            VENV_NEEDS_RECREATE=true
        else
            echo "✅ Venv создан с --system-site-packages"
            VENV_NEEDS_RECREATE=false
        fi
    else
        echo "⚠️  Не удалось проверить конфигурацию venv"
        VENV_NEEDS_RECREATE=false
    fi
fi

# Пересоздаем venv если нужно
if [ "$VENV_NEEDS_RECREATE" = true ]; then
    echo ""
    echo "🔄 Пересоздание venv с --system-site-packages..."
    DETECTION_DIR_ABS=$(pwd)
    cd ../..
    PROJECT_ROOT_ABS=$(pwd)
    echo "   Удаляю старый venv..."
    rm -rf venv
    echo "   Создаю новый venv с --system-site-packages..."
    python3 -m venv venv --system-site-packages || {
        echo "❌ Ошибка создания venv"
        exit 1
    }
    cd services/detection
    echo "✅ Venv пересоздан с --system-site-packages"
    echo "   📁 Вернулся в: $(pwd)"
    # После пересоздания нужно будет установить зависимости заново
    VENV_RECREATED=true
else
    VENV_RECREATED=false
fi

# Активируем venv
echo "🔌 Активация виртуального окружения..."
source ../../venv/bin/activate || {
    echo "❌ Ошибка активации venv"
    exit 1
}

# Проверяем, что мы в правильной директории
CURRENT_DIR=$(pwd)
echo "📁 Текущая директория: $CURRENT_DIR"

# Проверяем доступность pip
if ! command -v pip &> /dev/null; then
    echo "❌ pip не найден в venv"
    exit 1
fi
echo "✅ pip доступен: $(which pip)"

# Проверяем какие пакеты уже доступны из системы
echo "🔍 Проверка доступных системных пакетов..."
python -c "
import sys
print(f'Python путь: {sys.prefix}')
print(f'Системные пакеты доступны: {hasattr(sys, \"real_prefix\") or sys.base_prefix != sys.prefix}')
" || {
    echo "⚠️  Ошибка при проверке Python окружения"
}

# Устанавливаем ТОЛЬКО недостающие пакеты
echo "📦 Установка недостающих пакетов..."

# Проверяем и устанавливаем только то, что действительно нужно
MISSING_PACKAGES=()

# Маппинг между именами импортов и именами пакетов для pip
declare -A PACKAGE_MAP=(
    ["cv2"]="opencv-python-headless"
    ["PIL"]="Pillow"
    ["flask"]="flask"
    ["numpy"]="numpy"
    ["ultralytics"]="ultralytics"
)

check_package() {
    local import_name=$1
    local package_name=${PACKAGE_MAP[$import_name]:-$import_name}
    
    # Используем || true чтобы не падать при ошибке импорта
    if python -c "import $import_name" 2>/dev/null; then
        echo "✅ $import_name - уже установлен"
        return 0
    else
        MISSING_PACKAGES+=($package_name)
        echo "❌ $import_name - требуется установка (пакет: $package_name)"
        return 1
    fi
}

echo ""
echo "🔍 Проверка ключевых пакетов:"
set +e  # Временно отключаем set -e для проверки пакетов
check_package flask
check_package cv2
check_package ultralytics
check_package numpy
check_package PIL
set -e  # Включаем обратно

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
                echo "   ⚠️  Это должно было быть исправлено автоматически выше"
                echo "   💡 Если проблема сохраняется, пересоздайте venv вручную:"
                echo "      cd ~/dc-detector && rm -rf venv && python3 -m venv venv --system-site-packages"
            fi
        fi
    else
        echo "   ❌ picamera2 не установлен системно"
        echo "   💡 Установите: sudo apt install python3-picamera2"
    fi
fi

# Устанавливаем только недостающие пакеты
if [ ${#MISSING_PACKAGES[@]} -gt 0 ] || [ "$VENV_RECREATED" = true ]; then
    if [ "$VENV_RECREATED" = true ]; then
        echo ""
        echo "📥 Устанавливаю зависимости (venv был пересоздан)..."
        # Убеждаемся, что мы в правильной директории
        if [ ! -d "services/detection" ] && [ -d "../../services/detection" ]; then
            cd ../../services/detection
            echo "   Перешел в services/detection"
        fi
        
        # Проверяем путь к requirements.txt (он должен быть в services/detection)
        REQ_FILE=""
        if [ -f "requirements.txt" ]; then
            REQ_FILE="requirements.txt"
            echo "   ✅ Найден requirements.txt в текущей директории: $(pwd)"
        elif [ -f "services/detection/requirements.txt" ]; then
            REQ_FILE="services/detection/requirements.txt"
            echo "   ✅ Найден requirements.txt в services/detection"
        elif [ -f "../../services/detection/requirements.txt" ]; then
            REQ_FILE="../../services/detection/requirements.txt"
            echo "   ✅ Найден requirements.txt относительно текущей директории"
        fi
        
        if [ -n "$REQ_FILE" ] && [ -f "$REQ_FILE" ]; then
            echo "   📦 Установка из $REQ_FILE..."
            pip install -q -r "$REQ_FILE" || {
                echo "⚠️  Ошибка при установке из requirements.txt, пробую установить основные пакеты..."
                pip install -q flask opencv-python-headless numpy requests Pillow urllib3 Werkzeug || true
            }
        else
            echo "   ⚠️  requirements.txt не найден, устанавливаю основные пакеты..."
            pip install -q flask opencv-python-headless numpy requests Pillow urllib3 Werkzeug || true
            # Пытаемся установить ultralytics отдельно (может быть долго)
            echo "   📦 Установка ultralytics (это может занять время)..."
            pip install -q ultralytics || echo "⚠️  Не удалось установить ultralytics"
        fi
    else
        echo ""
        echo "📥 Устанавливаю недостающие пакеты: ${MISSING_PACKAGES[*]}"
        pip install -q "${MISSING_PACKAGES[@]}" || {
            echo "⚠️  Ошибка при установке некоторых пакетов"
        }
    fi
    echo "✅ Зависимости установлены"
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

# Убеждаемся, что мы в корне проекта
cd "$PROJECT_ROOT"
echo "📁 Переход в корень проекта: $(pwd)"

# Переходим в services/detection
cd services/detection || {
    echo "❌ Ошибка: не удалось перейти в services/detection"
    exit 1
}
echo "📁 Текущая директория: $(pwd)"

# Проверяем наличие detection_server.py
if [ ! -f "detection_server.py" ]; then
    echo "❌ Ошибка: detection_server.py не найден в $(pwd)"
    exit 1
fi

# Запускаем напрямую с активированным venv
echo "🔌 Активация venv перед запуском..."
source ../../venv/bin/activate || {
    echo "❌ Ошибка активации venv"
    exit 1
}

# Проверяем, что Python доступен
if ! command -v python &> /dev/null; then
    echo "❌ Python не найден в venv"
    exit 1
fi

echo "🐍 Python: $(which python)"
echo "🚀 Запуск detection_server.py..."
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
        tail -25 "../../.detection.log"
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