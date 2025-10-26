#!/bin/bash

# 🔥 DC-Detector - Простая установка
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

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Обновление системы
update_system() {
    print_info "Обновление системы..."
    sudo apt update
    sudo apt upgrade -y
        print_success "Система обновлена"
}

# Установка зависимостей
install_dependencies() {
    print_info "Установка зависимостей..."
    
    sudo apt install -y \
        python3-pip \
        python3-venv \
        python3-dev \
        python3-opencv \
        libopencv-dev \
        libhdf5-dev \
        libhdf5-serial-dev \
        libatlas-base-dev \
        libavcodec-dev \
        libavformat-dev \
        libswscale-dev \
        libv4l-dev \
        libxvidcore-dev \
        libx264-dev \
        libgtk-3-dev \
        libdc1394-dev \
        v4l-utils \
        git \
        wget \
        curl \
        build-essential \
        cmake \
        pkg-config \
        libjpeg-dev \
        libpng-dev \
        libtiff-dev \
        libwebp-dev \
        libopenexr-dev \
        libcamera-tools \
        libcamera-dev \
        python3-libcamera
    
    print_success "Зависимости установлены"
}

# Настройка камеры
setup_camera() {
    print_info "Настройка камеры..."
    
    # Включение камеры через raspi-config
    sudo raspi-config nonint do_camera 0
    
    # Проверка камеры
    if command -v vcgencmd >/dev/null 2>&1; then
        local camera_status=$(vcgencmd get_camera 2>/dev/null || echo "supported=0 detected=0")
        if echo "$camera_status" | grep -q "supported=1 detected=1"; then
            print_success "Камера настроена и обнаружена"
        else
            print_info "Камера настроена, но не обнаружена. Перезагрузите систему."
        fi
    fi
}

# Создание виртуального окружения
create_venv() {
    print_info "Создание виртуального окружения..."
    
    if [ -d "venv" ]; then
        print_info "Удаление существующего окружения..."
        rm -rf venv
    fi
    
    python3 -m venv venv
    source venv/bin/activate
    
    # Обновление pip
    pip install --upgrade pip

# Установка Python зависимостей
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    else
        pip install opencv-python ultralytics flask numpy pillow
    fi
    
    print_success "Виртуальное окружение создано"
}

# Проверка установки
verify_installation() {
    print_info "Проверка установки..."
    
    source venv/bin/activate
    
    # Проверка модулей
    python3 -c "import cv2, ultralytics, flask, numpy" || {
        print_error "Не все модули установлены"
        exit 1
    }
    
    print_success "Все модули установлены корректно"
}

# Основная функция
main() {
    print_header "DC-Detector - Установка"
    
    update_system
    install_dependencies
    setup_camera
    create_venv
    verify_installation
    
    print_header "Установка завершена!"
    print_success "Теперь запустите: ./start.sh"
}

main "$@"
