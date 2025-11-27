#!/bin/bash
# Скрипт для обновления проекта на проде (git pull + перезапуск)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🔄 Обновление проекта на проде..."
echo ""

cd "$PROJECT_ROOT"

# Проверяем, что это git репозиторий
if [ ! -d ".git" ]; then
    echo "❌ Это не git репозиторий"
    exit 1
fi

# Останавливаем сервисы
echo "🛑 Остановка сервисов..."
"$SCRIPT_DIR/stop-prod.sh"

# Обновляем код
echo ""
echo "📥 Обновление кода из git..."
git pull

# Перезапускаем сервисы
echo ""
echo "🚀 Перезапуск сервисов..."
"$SCRIPT_DIR/start-prod.sh"

echo ""
echo "✅ Обновление завершено!"

