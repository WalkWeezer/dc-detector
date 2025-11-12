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

# Проверяем наличие Flask
if ! python3 -c "import flask" 2>/dev/null; then
    echo "⚠️  Flask не установлен. Устанавливаю..."
    pip3 install flask || {
        echo "❌ Не удалось установить Flask"
        exit 1
    }
fi

echo "✅ Flask доступен"

# Создаем виртуальное окружение (опционально, но рекомендуется)
if [ ! -d "venv" ]; then
    echo "📦 Создаю виртуальное окружение..."
    python3 -m venv venv
fi

# Активируем виртуальное окружение
if [ -f "venv/bin/activate" ]; then
    echo "🔌 Активирую виртуальное окружение..."
    source venv/bin/activate
    
    # Устанавливаем зависимости
    echo "📦 Устанавливаю зависимости..."
    pip install flask || echo "⚠️  Flask уже установлен"
else
    echo "⚠️  Виртуальное окружение не найдено, используем системный Python"
fi

# Переходим в директорию detection service
cd services/detection

echo "🎬 Запускаю detection_server.py..."
echo "📍 Сервис будет доступен на http://0.0.0.0:8001"
echo "📍 Видеопоток: http://localhost:8001/video_feed_raw"
echo "📍 Health check: http://localhost:8001/health"
echo ""
echo "Для остановки нажмите Ctrl+C"
echo ""

# Запускаем скрипт
python3 detection_server.py

