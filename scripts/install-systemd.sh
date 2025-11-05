#!/bin/bash
# Скрипт установки systemd service для автозапуска DC-Detector на Raspberry Pi

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICE_FILE="$PROJECT_ROOT/systemd/dc-detector.service"
SYSTEMD_DIR="/etc/systemd/system"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Этот скрипт должен быть запущен от имени root (используйте sudo)"
    exit 1
fi

# Проверка наличия service файла
if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ Service файл не найден: $SERVICE_FILE"
    exit 1
fi

# Определение пути к проекту
# Пользователь может указать путь через переменную окружения
PROJECT_PATH="${DC_DETECTOR_PATH:-$PROJECT_ROOT}"

# Создание временного service файла с правильным путем
TEMP_SERVICE=$(mktemp)
sed "s|/opt/dc-detector|$PROJECT_PATH|g" "$SERVICE_FILE" > "$TEMP_SERVICE"

echo "📋 Установка systemd service..."
echo "   Путь к проекту: $PROJECT_PATH"

# Копирование service файла
cp "$TEMP_SERVICE" "$SYSTEMD_DIR/dc-detector.service"
rm "$TEMP_SERVICE"

# Перезагрузка systemd
systemctl daemon-reload

# Включение автозапуска
systemctl enable dc-detector.service

echo "✅ Systemd service установлен и включен"
echo ""
echo "📝 Полезные команды:"
echo "   Запуск:   sudo systemctl start dc-detector"
echo "   Остановка: sudo systemctl stop dc-detector"
echo "   Статус:   sudo systemctl status dc-detector"
echo "   Логи:     sudo journalctl -u dc-detector -f"
echo ""
echo "⚠️  Для изменения пути к проекту используйте:"
echo "   export DC_DETECTOR_PATH=/path/to/project"
echo "   sudo -E $0"

