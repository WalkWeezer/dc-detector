#!/bin/bash

# 🔥 DC-Detector - Установка совместимых пакетов для Raspberry Pi
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

# Установка совместимых пакетов для Raspberry Pi
install_compatible_packages() {
    print_info "Установка совместимых пакетов для Raspberry Pi..."
    
    # Активация виртуального окружения
    source venv/bin/activate
    
    # Обновление pip
    print_info "Обновление pip..."
    pip install --upgrade pip
    
    # Установка основных пакетов по одному для лучшего контроля
    print_info "Установка numpy..."
    pip install numpy==1.24.3
    
    print_info "Установка pillow..."
    pip install pillow==10.0.1
    
    print_info "Установка flask..."
    pip install flask==2.3.3
    
    print_info "Установка opencv-python..."
    pip install opencv-python==4.8.1.78
    
    print_info "Установка ultralytics (YOLO)..."
    pip install ultralytics==8.0.196
    
    print_info "Установка picamera2..."
    pip install picamera2==0.3.12
    
    print_info "Установка дополнительных утилит..."
    pip install psutil==5.9.5
    pip install gpiozero==1.6.2
    
    # Опциональные пакеты для WebSocket
    print_info "Установка WebSocket пакетов..."
    pip install python-socketio==5.8.0
    pip install eventlet==0.33.3
    
    print_success "Все совместимые пакеты установлены"
}

# Проверка установки
verify_installation() {
    print_info "Проверка установки..."
    
    # Активация виртуального окружения
    source venv/bin/activate
    
    # Проверка основных модулей
    local modules=("cv2" "ultralytics" "flask" "numpy" "picamera2")
    local missing_modules=()
    
    for module in "${modules[@]}"; do
        if python3 -c "import $module" 2>/dev/null; then
            print_success "Модуль $module установлен"
        else
            print_error "Модуль $module не найден"
            missing_modules+=("$module")
        fi
    done
    
    if [ ${#missing_modules[@]} -ne 0 ]; then
        print_error "Отсутствуют модули: ${missing_modules[*]}"
        return 1
    fi
    
    print_success "Все основные модули установлены корректно"
}

# Основная функция
main() {
    print_header "DC-Detector - Установка совместимых пакетов"
    
    # Проверка виртуального окружения
    if [ ! -d "venv" ]; then
        print_error "Виртуальное окружение не найдено"
        print_info "Сначала запустите: ./setup.sh"
        exit 1
    fi
    
    install_compatible_packages
    verify_installation
    
    print_header "Установка завершена!"
    print_success "Теперь запустите: ./start.sh"
}

main "$@"
