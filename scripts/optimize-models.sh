#!/bin/bash
# Скрипт для автоматической конвертации всех моделей в оптимизированные форматы

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODELS_DIR="$PROJECT_ROOT/services/detection/models"
PYTHON_SCRIPT="$PROJECT_ROOT/services/detection/scripts/optimize_models.py"

echo "🔍 Поиск моделей в $MODELS_DIR"

if [ ! -d "$MODELS_DIR" ]; then
    echo "❌ Каталог моделей не найден: $MODELS_DIR"
    exit 1
fi

if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "❌ Скрипт конвертации не найден: $PYTHON_SCRIPT"
    exit 1
fi

# Находим все .pt модели
MODELS=$(find "$MODELS_DIR" -name "*.pt" -type f)

if [ -z "$MODELS" ]; then
    echo "⚠️  Модели .pt не найдены в $MODELS_DIR"
    exit 0
fi

echo "📦 Найдено моделей: $(echo "$MODELS" | wc -l)"
echo ""

# Конвертируем каждую модель
for MODEL in $MODELS; do
    MODEL_NAME=$(basename "$MODEL")
    ONNX_PATH="${MODEL%.pt}.onnx"
    
    # Пропускаем если ONNX уже существует
    if [ -f "$ONNX_PATH" ]; then
        echo "⏭️  Пропуск $MODEL_NAME (ONNX уже существует)"
        continue
    fi
    
    echo "🔄 Конвертация $MODEL_NAME в ONNX..."
    python3 "$PYTHON_SCRIPT" "$MODEL" --output "$ONNX_PATH" --imgsz 640
    
    if [ $? -eq 0 ]; then
        echo "✅ $MODEL_NAME успешно конвертирована"
    else
        echo "❌ Ошибка конвертации $MODEL_NAME"
    fi
    echo ""
done

echo "✨ Готово!"

