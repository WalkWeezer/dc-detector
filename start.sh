#!/bin/bash

# 🔥 DC-Detector - Простой запуск
# Автор: DC-Detector Team

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Проверка файлов
check_files() {
    if [ ! -f "app_pi.py" ] || [ ! -f "config_pi.py" ] || [ ! -f "bestfire.pt" ]; then
        print_error "Отсутствуют файлы приложения"
        print_info "Убедитесь, что вы находитесь в директории проекта"
        exit 1
    fi
}

# Создание и активация виртуального окружения
setup_venv() {
    print_info "Настройка виртуального окружения..."
    
    # Удаление старого окружения если есть
    if [ -d "venv" ]; then
        print_info "Удаление старого виртуального окружения..."
        rm -rf venv
    fi
    
    # Создание нового виртуального окружения
    print_info "Создание виртуального окружения..."
    python3 -m venv venv
    
    # Активация виртуального окружения
    print_info "Активация виртуального окружения..."
    source venv/bin/activate
    
    # Обновление pip
    print_info "Обновление pip..."
    pip install --upgrade pip
    
    # Установка зависимостей
    print_info "Установка зависимостей..."
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    else
        pip install opencv-python ultralytics flask numpy pillow
    fi
    
    print_success "Виртуальное окружение создано и настроено"
}

# Проверка камеры
check_camera() {
    print_info "Проверка камеры..."
    
    if command -v vcgencmd >/dev/null 2>&1; then
        local camera_status=$(vcgencmd get_camera 2>/dev/null || echo "supported=0 detected=0")
        if echo "$camera_status" | grep -q "supported=1 detected=1"; then
            print_success "Камера обнаружена"
        else
            print_warning "Камера не обнаружена: $camera_status"
        fi
    fi
}

# Запуск приложения
start_app() {
    print_header "Запуск DC-Detector"
    
    # Проверка модулей (виртуальное окружение уже активировано)
    python3 -c "import cv2, ultralytics, flask, numpy" || {
        print_error "Не все модули установлены"
        exit 1
    }
    
    print_success "Все проверки пройдены"
    print_info "Запуск приложения..."
    echo ""
    print_info "Веб-интерфейс будет доступен по адресу:"
    print_info "http://localhost:5000"
    print_info "http://$(hostname -I | awk '{print $1}'):5000"
    echo ""
    print_info "Для остановки нажмите Ctrl+C"
    echo ""
    
    # Запуск приложения
    python3 app_pi.py
}

# Основная функция
main() {
    check_files
    setup_venv
    check_camera
    start_app
}

# Обработка сигналов
trap 'echo -e "\n${YELLOW}Остановка...${NC}"; exit 0' INT TERM

main "$@"
