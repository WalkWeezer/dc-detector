#!/bin/sh
# Entrypoint скрипт для backend контейнера
# Создает необходимые директории если они не существуют

set -e

# Создание директорий для данных
mkdir -p /app/data/detections/saved

# Запуск приложения
exec "$@"

