#!/bin/bash
# Скрипт для прямого запуска detection service на Raspberry Pi

set -e

echo "🚀 Запуск Detection Service напрямую (без Docker)"

# Проверяем, что мы на Raspberry Pi
if [ ! -f /proc/device-tree/model ] || ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "⚠️  Внимание: скрипт предназначен для запуска на Raspberry Pi"
fi

# Переходим в директорию проекта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "📁 Рабочая директория: $PROJECT_DIR"

# Проверяем наличие Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не найден. Установите: sudo apt install python3 python3-pip"
    exit 1
fi

echo "✅ Python 3 найден: $(python3 --version)"

# Проверяем наличие picamera2
if ! python3 -c "import picamera2" 2>/dev/null; then
    echo "⚠️  picamera2 не установлен. Устанавливаю..."
    sudo apt update
    sudo apt install -y python3-picamera2 || {
        echo "❌ Не удалось установить python3-picamera2"
        exit 1
    }
fi

echo "✅ picamera2 доступен"

# Проверяем наличие python3-venv
if ! python3 -m venv --help &> /dev/null; then
    echo "⚠️  python3-venv не найден. Устанавливаю..."
    sudo apt install -y python3-venv python3-full || {
        echo "❌ Не удалось установить python3-venv"
        exit 1
    }
fi

# Создаем виртуальное окружение (обязательно для современных версий Raspberry Pi OS)
if [ ! -d "venv" ]; then
    echo "📦 Создаю виртуальное окружение..."
    python3 -m venv venv || {
        echo "❌ Не удалось создать виртуальное окружение"
        exit 1
    }
fi

# Активируем виртуальное окружение
if [ -f "venv/bin/activate" ]; then
    echo "🔌 Активирую виртуальное окружение..."
    source venv/bin/activate
    
    # Обновляем pip в виртуальном окружении
    echo "📦 Обновляю pip..."
    pip install --upgrade pip --quiet
    
    # Проверяем и устанавливаем зависимости
    echo "📦 Проверяю зависимости..."
    
    if ! python -c "import flask" 2>/dev/null; then
        echo "⚠️  Flask не установлен. Устанавливаю..."
        pip install flask || {
            echo "❌ Не удалось установить Flask"
            exit 1
        }
    fi
    
    if ! python -c "import cv2" 2>/dev/null; then
        echo "⚠️  OpenCV не установлен. Устанавливаю..."
        pip install opencv-python || {
            echo "❌ Не удалось установить opencv-python"
            echo "💡 Попробуйте установить через apt: sudo apt install python3-opencv"
            exit 1
        }
    fi
    
    if ! python -c "from ultralytics import YOLO" 2>/dev/null; then
        echo "⚠️  Ultralytics YOLO не установлен. Устанавливаю..."
        pip install ultralytics || {
            echo "❌ Не удалось установить ultralytics"
            echo "💡 Детекция будет отключена"
        }
    fi
    
    echo "✅ Все зависимости установлены"
else
    echo "❌ Не удалось создать виртуальное окружение"
    exit 1
fi

# Переходим в директорию detection service
cd services/detection

# Проверяем, не запущен ли уже процесс на порту 8001
if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Порт 8001 уже занят!"
    echo "💡 Остановите процесс или используйте другой порт:"
    echo "   PORT=8080 python detection_server.py"
    echo ""
    echo "Или остановите процесс на порту 8001:"
    PID=$(lsof -Pi :8001 -sTCP:LISTEN -t 2>/dev/null)
    if [ ! -z "$PID" ]; then
        echo "   Найден процесс с PID: $PID"
        echo "   Остановить: kill $PID"
    fi
    exit 1
fi

echo "🎬 Запускаю detection_server.py..."
echo "📍 Сервис будет доступен на http://0.0.0.0:8001"
echo "📍 Видеопоток: http://localhost:8001/video_feed_raw"
echo "📍 Health check: http://localhost:8001/health"
echo ""
echo "Для остановки нажмите Ctrl+C"
echo ""

# Запускаем скрипт (используем python из venv)
python detection_server.py

