#!/bin/bash

# 🔥 DC-Detector - Быстрый запуск без виртуального окружения
# Автор: DC-Detector Team
# Версия: 1.0

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для вывода
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

# Проверка основных файлов
check_files() {
    local missing_files=()
    
    if [ ! -f "app_pi.py" ]; then
        missing_files+=("app_pi.py")
    fi
    
    if [ ! -f "config_pi.py" ]; then
        missing_files+=("config_pi.py")
    fi
    
    if [ ! -f "bestfire.pt" ]; then
        missing_files+=("bestfire.pt")
    fi
    
    if [ ${#missing_files[@]} -ne 0 ]; then
        print_error "Отсутствуют файлы: ${missing_files[*]}"
        print_info "Убедитесь, что вы находитесь в правильной директории проекта"
        exit 1
    fi
}

# Проверка Python модулей
check_python_modules() {
    print_info "Проверка Python модулей..."
    
    local modules=("cv2" "ultralytics" "flask" "numpy")
    local missing_modules=()
    
    for module in "${modules[@]}"; do
        if python3 -c "import $module" 2>/dev/null; then
            print_success "Модуль $module найден"
        else
            print_error "Модуль $module не найден"
            missing_modules+=("$module")
        fi
    done
    
    if [ ${#missing_modules[@]} -ne 0 ]; then
        print_error "Отсутствуют модули: ${missing_modules[*]}"
        print_info "Установите недостающие модули:"
        echo "  pip3 install ${missing_modules[*]}"
        echo ""
        print_info "Или создайте виртуальное окружение:"
        echo "  ./create_venv.sh"
        exit 1
    fi
}

# Проверка камеры
check_camera() {
    print_info "Проверка камеры..."
    
    # Проверка через vcgencmd
    if command -v vcgencmd >/dev/null 2>&1; then
        local camera_status=$(vcgencmd get_camera 2>/dev/null || echo "supported=0 detected=0")
        if echo "$camera_status" | grep -q "supported=1 detected=1"; then
            print_success "Камера обнаружена через vcgencmd"
        else
            print_warning "Камера не обнаружена через vcgencmd: $camera_status"
        fi
    fi
    
    # Проверка через libcamera
    if command -v libcamera-hello >/dev/null 2>&1; then
        if libcamera-hello --list-cameras 2>/dev/null | grep -q "Available cameras"; then
            print_success "Камера обнаружена через libcamera"
        else
            print_warning "Камера не обнаружена через libcamera"
        fi
    fi
}

# Запуск приложения
start_application() {
    print_header "Запуск DC-Detector"
    
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
    print_header "DC-Detector - Быстрый запуск"
    
    check_files
    check_python_modules
    check_camera
    
    start_application
}

# Обработка сигналов
trap 'echo -e "\n${YELLOW}Получен сигнал остановки...${NC}"; exit 0' INT TERM

# Запуск
main "$@"
