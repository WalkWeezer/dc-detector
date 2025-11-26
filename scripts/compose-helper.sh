#!/bin/bash
# Утилита для определения правильного Docker Compose файла
# Используется всеми скриптами для единообразного выбора compose файла

# Определяет, какой compose файл использовать
# Возвращает аргументы для docker compose
get_compose_files() {
    local project_root="${1:-$(pwd)}"
    local env="${2:-prod}"
    
    # Для dev окружения используем dev override
    if [ "$env" = "dev" ] && [ -f "$project_root/docker-compose.dev.yml" ]; then
        echo "-f $project_root/docker-compose.yml -f $project_root/docker-compose.dev.yml"
        return 0
    fi
    
    # Для production используем prod файл (приоритет)
    if [ -f "$project_root/docker-compose.prod.yml" ]; then
        echo "-f $project_root/docker-compose.prod.yml"
        return 0
    fi
    
    # Fallback на базовый файл
    if [ -f "$project_root/docker-compose.yml" ]; then
        echo "-f $project_root/docker-compose.yml"
        return 0
    fi
    
    # Если ничего не найдено
    echo ""
    return 1
}

# Получает compose файлы и выполняет команду
exec_compose() {
    local project_root="${1:-$(pwd)}"
    shift
    local compose_args=$(get_compose_files "$project_root")
    
    if [ -z "$compose_args" ]; then
        echo "❌ Docker Compose файлы не найдены в $project_root" >&2
        return 1
    fi
    
    docker compose $compose_args "$@"
}

# Если скрипт запущен напрямую, выводим информацию
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    PROJECT_ROOT="${1:-$(pwd)}"
    echo "Compose файлы для $PROJECT_ROOT:"
    get_compose_files "$PROJECT_ROOT"
fi

