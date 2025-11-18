#!/bin/bash
# Скрипт установки systemd services для автозапуска DC-Detector на Raspberry Pi
# Устанавливает два сервиса:
# - dc-detection.service - Detection Service (запускается отдельно от Docker)
# - dc-detector.service - Backend и Frontend (Docker Compose)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DETECTION_SERVICE_FILE="$PROJECT_ROOT/systemd/dc-detection.service"
DOCKER_SERVICE_FILE="$PROJECT_ROOT/systemd/dc-detector.service"
SYSTEMD_DIR="/etc/systemd/system"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Этот скрипт должен быть запущен от имени root (используйте sudo)"
    exit 1
fi

# Проверка наличия service файлов
if [ ! -f "$DETECTION_SERVICE_FILE" ]; then
    echo "❌ Service файл не найден: $DETECTION_SERVICE_FILE"
    exit 1
fi

if [ ! -f "$DOCKER_SERVICE_FILE" ]; then
    echo "❌ Service файл не найден: $DOCKER_SERVICE_FILE"
    exit 1
fi

# Определение пути к проекту
# Пользователь может указать путь через переменную окружения
PROJECT_PATH="${DC_DETECTOR_PATH:-$PROJECT_ROOT}"

# Определение пользователя (по умолчанию pi, можно указать через переменную)
SERVICE_USER="${DC_DETECTOR_USER:-pi}"

echo "📋 Установка systemd services..."
echo "   Путь к проекту: $PROJECT_PATH"
echo "   Пользователь: $SERVICE_USER"
echo ""

# Установка Detection Service
echo "🔧 Установка dc-detection.service (Detection Service)..."
TEMP_DETECTION=$(mktemp)
sed -e "s|/opt/dc-detector|$PROJECT_PATH|g" \
    -e "s|User=pi|User=$SERVICE_USER|g" \
    "$DETECTION_SERVICE_FILE" > "$TEMP_DETECTION"

cp "$TEMP_DETECTION" "$SYSTEMD_DIR/dc-detection.service"
rm "$TEMP_DETECTION"

# Установка Docker Compose Service
echo "🔧 Установка dc-detector.service (Backend/Frontend Docker)..."
TEMP_DOCKER=$(mktemp)
sed "s|/opt/dc-detector|$PROJECT_PATH|g" "$DOCKER_SERVICE_FILE" > "$TEMP_DOCKER"

cp "$TEMP_DOCKER" "$SYSTEMD_DIR/dc-detector.service"
rm "$TEMP_DOCKER"

# Перезагрузка systemd
systemctl daemon-reload

# Включение автозапуска
systemctl enable dc-detection.service
systemctl enable dc-detector.service

echo ""
echo "✅ Systemd services установлены и включены"
echo ""
echo "📝 Полезные команды:"
echo ""
echo "   Detection Service:"
echo "   Запуск:   sudo systemctl start dc-detection"
echo "   Остановка: sudo systemctl stop dc-detection"
echo "   Статус:   sudo systemctl status dc-detection"
echo "   Логи:     sudo journalctl -u dc-detection -f"
echo ""
echo "   Backend/Frontend (Docker):"
echo "   Запуск:   sudo systemctl start dc-detector"
echo "   Остановка: sudo systemctl stop dc-detector"
echo "   Статус:   sudo systemctl status dc-detector"
echo "   Логи:     sudo journalctl -u dc-detector -f"
echo ""
echo "⚠️  Для изменения пути к проекту используйте:"
echo "   export DC_DETECTOR_PATH=/path/to/project"
echo "   export DC_DETECTOR_USER=username"
echo "   sudo -E $0"

