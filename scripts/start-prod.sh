#!/bin/bash
# Скрипт запуска всей системы для продакшна на Raspberry Pi
# Оптимизированная версия с --system-site-packages
#
# Использование:
#   ./scripts/start-prod.sh          # Обычный запуск
#   ./scripts/start-prod.sh --rebuild-frontend  # Принудительная пересборка фронтенда

set -e

# Проверяем флаги
FORCE_REBUILD_FRONTEND=false
if [[ "$*" == *"--rebuild-frontend"* ]]; then
    FORCE_REBUILD_FRONTEND=true
fi

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
check_command node "Node.js"
check_command npm "npm"

# Проверка и освобождение портов
echo ""
echo "🔍 Проверка портов..."

kill_port() {
    local port=$1
    local name=$2
    local pids=$(lsof -ti :$port 2>/dev/null || true)
    
    if [ -z "$pids" ]; then
        echo "✅ Порт $port ($name) свободен"
        return 0
    else
        echo "⚠️  Порт $port ($name) занят, останавливаю процессы..."
        for pid in $pids; do
            if kill -0 $pid 2>/dev/null; then
                echo "   🛑 Останавливаю процесс PID: $pid"
                kill -TERM $pid 2>/dev/null || true
                sleep 1
                # Если процесс не остановился, убиваем принудительно
                if kill -0 $pid 2>/dev/null; then
                    echo "   💀 Принудительная остановка PID: $pid"
                    kill -KILL $pid 2>/dev/null || true
                fi
            fi
        done
        sleep 1
        # Проверяем еще раз
        if lsof -ti :$port >/dev/null 2>&1; then
            echo "   ⚠️  Порт $port все еще занят, повторная попытка..."
            sleep 2
            pids=$(lsof -ti :$port 2>/dev/null || true)
            for pid in $pids; do
                kill -KILL $pid 2>/dev/null || true
            done
        fi
        echo "   ✅ Порт $port освобожден"
        return 0
    fi
}

kill_port 8001 "Detection Service"
kill_port 8080 "Backend"
# Frontend больше не использует отдельный порт, отдается через Backend

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
        echo "🛑 Останавливаю предыдущий Detection Service (PID: $OLD_PID)..."
        kill -TERM $OLD_PID 2>/dev/null || true
        sleep 2
        # Принудительная остановка если не остановился
        if kill -0 $OLD_PID 2>/dev/null; then
            echo "   💀 Принудительная остановка..."
            kill -KILL $OLD_PID 2>/dev/null || true
        fi
    fi
    rm -f .detection.pid
fi

# Дополнительная проверка порта 8001
if lsof -ti :8001 >/dev/null 2>&1; then
    echo "🛑 Останавливаю процессы на порту 8001..."
    lsof -ti :8001 | xargs kill -KILL 2>/dev/null || true
    sleep 1
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
# Загружаем переменные окружения из .env для detection service
# ВАЖНО: Detection service должен использовать PORT=8001, не 8080!
if [ -f "../../.env" ]; then
    # Безопасная загрузка переменных из .env (только нужные для detection service)
    set -a
    # Загружаем только нужные переменные для detection service
    while IFS= read -r line; do
        # Пропускаем пустые строки и комментарии
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        # Проверяем что строка содержит = и начинается с нужного ключа
        [[ "$line" =~ = ]] || continue
        key="${line%%=*}"
        value="${line#*=}"
        # Убираем пробелы из ключа
        key=$(echo "$key" | xargs)
        # Проверяем что это нужная переменная
        [[ "$key" =~ ^(CAMERA_INDEX|CONFIDENCE_THRESHOLD|INFER_FPS|ROTATE_ANGLE|FLIP_HORIZONTAL|FLIP_VERTICAL)$ ]] || continue
        # Проверяем что ключ валидный
        [[ "$key" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]] || continue
        # Экспортируем переменную
        export "$key=$value" 2>/dev/null || true
    done < <(grep -v '^#' ../../.env | grep -v '^$')
    set +a
    # Явно устанавливаем PORT=8001 для detection service (не берем из .env, т.к. там может быть 8080 для backend)
    export PORT=8001
fi
# Если .env нет, устанавливаем PORT=8001 по умолчанию
export PORT=${PORT:-8001}
echo "   PORT для Detection Service: $PORT"
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

# ЗАПУСК BACKEND
echo ""
echo "🚀 Запуск Backend..."

# Остановка предыдущего процесса Backend
if [ -f ".backend.pid" ]; then
    OLD_PID=$(cat .backend.pid)
    if kill -0 $OLD_PID 2>/dev/null; then
        echo "🛑 Останавливаю предыдущий Backend (PID: $OLD_PID)..."
        kill -TERM $OLD_PID 2>/dev/null || true
        sleep 2
        # Принудительная остановка если не остановился
        if kill -0 $OLD_PID 2>/dev/null; then
            echo "   💀 Принудительная остановка..."
            kill -KILL $OLD_PID 2>/dev/null || true
            sleep 1
        fi
    fi
    rm -f .backend.pid
fi

# Улучшенная остановка процессов на порту 8080
echo "🛑 Проверка и остановка процессов на порту 8080..."
PIDS_ON_8080=$(lsof -ti :8080 2>/dev/null || true)
if [ ! -z "$PIDS_ON_8080" ]; then
    echo "   Найдены процессы на порту 8080:"
    echo "$PIDS_ON_8080" | while read pid; do
        if [ ! -z "$pid" ]; then
            ps -p $pid -o pid,cmd --no-headers 2>/dev/null || echo "   PID $pid (процесс не найден)"
        fi
    done
    echo "   Останавливаю все процессы..."
fi

for i in {1..5}; do
    PIDS_ON_8080=$(lsof -ti :8080 2>/dev/null || true)
    if [ ! -z "$PIDS_ON_8080" ]; then
        echo "   Попытка $i/5: остановка процессов..."
        # Сначала мягкая остановка
        echo "$PIDS_ON_8080" | xargs kill -TERM 2>/dev/null || true
        sleep 2
        # Если все еще занят - принудительная остановка
        PIDS_ON_8080=$(lsof -ti :8080 2>/dev/null || true)
        if [ ! -z "$PIDS_ON_8080" ]; then
            echo "   Принудительная остановка (KILL)..."
            echo "$PIDS_ON_8080" | xargs kill -KILL 2>/dev/null || true
            sleep 1
        fi
    else
        if [ $i -gt 1 ]; then
            echo "   ✅ Порт 8080 освобожден"
        fi
        break
    fi
done

# Финальная проверка порта
PIDS_ON_8080=$(lsof -ti :8080 2>/dev/null || true)
if [ ! -z "$PIDS_ON_8080" ]; then
    echo "❌ ОШИБКА: Порт 8080 все еще занят после 5 попыток!"
    echo "   Запущенные процессы:"
    echo "$PIDS_ON_8080" | while read pid; do
        if [ ! -z "$pid" ]; then
            ps -p $pid -o pid,cmd --no-headers 2>/dev/null || echo "   PID $pid"
        fi
    done
    echo ""
    echo "   Попробуйте остановить процессы вручную:"
    echo "   kill -9 \$(lsof -ti :8080)"
    exit 1
fi

# Дополнительная проверка: убеждаемся что нет других Node процессов на 8080
sleep 1
PIDS_ON_8080=$(lsof -ti :8080 2>/dev/null || true)
if [ ! -z "$PIDS_ON_8080" ]; then
    echo "⚠️  ВНИМАНИЕ: На порту 8080 все еще есть процессы, но продолжаем..."
    echo "$PIDS_ON_8080" | while read pid; do
        ps -p $pid -o pid,cmd --no-headers 2>/dev/null || true
    done
fi

rm -f .backend.log

# Переходим в services/backend
cd services/backend || {
    echo "❌ Ошибка: не удалось перейти в services/backend"
    exit 1
}

# Проверяем наличие node_modules
if [ ! -d "node_modules" ]; then
    echo "📦 Установка зависимостей Backend..."
    npm install
fi

# Загружаем переменные окружения
if [ -f "../../.env" ]; then
    # Безопасная загрузка переменных из .env (игнорируем комментарии и пустые строки)
    set -a
    # Фильтруем только валидные строки переменных (KEY=VALUE) и экспортируем их
    while IFS= read -r line; do
        # Пропускаем пустые строки и комментарии
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        # Проверяем что строка содержит =
        [[ "$line" =~ = ]] || continue
        # Извлекаем ключ и значение
        key="${line%%=*}"
        value="${line#*=}"
        # Убираем пробелы из ключа
        key=$(echo "$key" | xargs)
        # Проверяем что ключ валидный (начинается с буквы или подчеркивания)
        [[ "$key" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]] || continue
        # Экспортируем переменную
        export "$key=$value" 2>/dev/null || true
    done < <(grep -v '^#' ../../.env | grep -v '^$')
    set +a
fi

# Финальная проверка перед запуском - порт должен быть свободен
FINAL_PIDS=$(lsof -ti :8080 2>/dev/null || true)
if [ ! -z "$FINAL_PIDS" ]; then
    echo "❌ КРИТИЧЕСКАЯ ОШИБКА: Порт 8080 все еще занят перед запуском Backend!"
    echo "   Процессы на порту 8080:"
    echo "$FINAL_PIDS" | while read pid; do
        if [ ! -z "$pid" ]; then
            ps -p $pid -o pid,cmd --no-headers 2>/dev/null || echo "   PID $pid"
        fi
    done
    echo ""
    echo "   Остановите процессы вручную:"
    echo "   kill -9 \$(lsof -ti :8080)"
    exit 1
fi

# Запускаем Backend
echo "🚀 Запуск Backend на порту ${PORT:-8080}..."
nohup npm start > "../../.backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "../../.backend.pid"
echo "✅ Backend запущен (PID: $BACKEND_PID)"

# Проверяем через 2 секунды, что запустился только один процесс
sleep 2
PIDS_ON_8080=$(lsof -ti :8080 2>/dev/null || true)
if [ ! -z "$PIDS_ON_8080" ]; then
    PID_COUNT=$(echo "$PIDS_ON_8080" | wc -l)
    if [ "$PID_COUNT" -gt 1 ]; then
        echo "⚠️  ВНИМАНИЕ: На порту 8080 обнаружено $PID_COUNT процессов (ожидался 1)!"
        echo "   Процессы:"
        echo "$PIDS_ON_8080" | while read pid; do
            if [ ! -z "$pid" ]; then
                ps -p $pid -o pid,cmd --no-headers 2>/dev/null || echo "   PID $pid"
            fi
        done
        echo "   Ожидаемый PID Backend: $BACKEND_PID"
    else
        ACTUAL_PID=$(echo "$PIDS_ON_8080" | head -1)
        if [ "$ACTUAL_PID" != "$BACKEND_PID" ]; then
            echo "⚠️  ВНИМАНИЕ: На порту 8080 процесс с другим PID ($ACTUAL_PID вместо $BACKEND_PID)"
        fi
    fi
fi

cd "$PROJECT_ROOT"

# ПОДГОТОВКА FRONTEND (отдается через Backend Express)
echo ""
echo "🌐 Подготовка Frontend..."

# Очищаем старые файлы и папку dist если есть
rm -f .frontend.pid .frontend.log .frontend-build.log
if [ -d "frontend/dist" ]; then
    echo "🗑️  Удаление старой папки frontend/dist..."
    rm -rf frontend/dist
fi

# Frontend теперь отдается через Backend Express напрямую из исходников
# НЕ используем Vite для продакшена
echo "✅ Frontend будет отдаваться напрямую из исходников (без сборки)"

# На проде НЕ используем Vite - отдаем исходники напрямую через Backend Express
# Удаляем старую сборку dist, если есть, чтобы всегда использовались исходники
if [ -d "frontend" ]; then
    if [ -d "frontend/dist" ]; then
        echo "🧹 Удаление старой сборки dist (на проде используем исходники)..."
        rm -rf frontend/dist
    fi
    echo "✅ Frontend будет отдаваться из исходников (без сборки Vite)"
fi

echo "ℹ️  Frontend будет отдаваться через Backend Express на порту ${BACKEND_PORT:-8080}"

echo "⏳ Ожидание запуска сервисов (5 секунд)..."
sleep 5

# ФИНАЛЬНАЯ ПРОВЕРКА
echo ""
echo "🔍 Финальная проверка сервисов..."

check_service() {
    local url=$1
    local name=$2
    local max_attempts=3
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s --connect-timeout 5 "$url" >/dev/null 2>&1; then
            echo "✅ $name"
            return 0
        fi
        if [ $attempt -lt $max_attempts ]; then
            sleep 2
        fi
        attempt=$((attempt + 1))
    done
    
    echo "⚠️  $name (не отвечает на $url)"
    return 1
}

check_service "http://localhost:8001/health" "Detection Service"
check_service "http://localhost:8080/health" "Backend"
# Frontend отдается через Backend, отдельная проверка не нужна

# ИТОГИ
echo ""
echo "============================================================"
echo "✨ Система запущена!"
echo "============================================================"
echo ""
echo "📍 Сервисы:"
echo "   • Frontend:  http://localhost:${BACKEND_PORT:-8080} (отдается через Backend)"
echo "   • Backend:   http://localhost:${BACKEND_PORT:-8080}" 
echo "   • Detection: http://localhost:8001"
echo ""
echo "📋 Полезные команды:"
echo "   • Логи Detection: tail -f .detection.log"
echo "   • Логи Backend:   tail -f .backend.log"
echo "   • Логи Frontend (сборка):  tail -f .frontend-build.log (если была сборка)"
echo "   • Остановка:      ./scripts/stop-prod.sh"
echo "   • Перезапуск:     ./scripts/stop-prod.sh && ./scripts/start-prod.sh"
echo ""