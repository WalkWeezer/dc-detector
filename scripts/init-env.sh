#!/bin/bash
# Скрипт для создания .env файла из env.example если он не существует

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ENV_FILE="$PROJECT_ROOT/.env"
ENV_EXAMPLE="$PROJECT_ROOT/env.example"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        echo "📋 Создание .env файла из env.example..."
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        echo "✅ .env файл создан"
    else
        echo "⚠️  env.example не найден, создаю пустой .env файл"
        touch "$ENV_FILE"
    fi
else
    echo "ℹ️  .env файл уже существует"
fi

