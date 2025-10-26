#!/bin/bash

# 🔥 DC-Detector - Установка системных зависимостей
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

# Установка системных зависимостей
install_system_dependencies() {
    print_info "Установка системных зависимостей..."
    
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
    
    print_success "Системные зависимости установлены"
}

# Создание виртуального окружения
create_venv() {
    print_info "Создание виртуального окружения..."
    
    # Удаление старого окружения если есть
    if [ -d "venv" ]; then
        print_info "Удаление старого виртуального окружения..."
        rm -rf venv
    fi
    
    # Создание нового виртуального окружения
    python3 -m venv venv
    
    if [ -d "venv" ]; then
        print_success "Виртуальное окружение создано"
    else
        print_error "Не удалось создать виртуальное окружение"
        exit 1
    fi
}

# Установка Python зависимостей
install_python_dependencies() {
    print_info "Установка Python зависимостей..."
    
    # Активация виртуального окружения
    source venv/bin/activate
    
    # Обновление pip
    print_info "Обновление pip..."
    pip install --upgrade pip
    
    # Установка зависимостей
    if [ -f "requirements.txt" ]; then
        print_info "Установка зависимостей из requirements.txt..."
        pip install -r requirements.txt
    else
        print_info "Установка основных зависимостей..."
        pip install opencv-python ultralytics flask numpy pillow
    fi
    
    print_success "Python зависимости установлены"
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

# Проверка установки
verify_installation() {
    print_info "Проверка установки..."
    
    # Проверка Python
    if command -v python3 >/dev/null 2>&1; then
        local python_version=$(python3 --version 2>&1)
        print_success "Python найден: $python_version"
    else
        print_error "Python3 не найден"
        exit 1
    fi
    
    # Проверка venv модуля
    if python3 -m venv --help >/dev/null 2>&1; then
        print_success "Модуль venv доступен"
    else
        print_error "Модуль venv не найден"
        exit 1
    fi
    
    # Проверка виртуального окружения
    if [ -d "venv" ]; then
        print_success "Виртуальное окружение найдено"
        
        # Проверка Python модулей в виртуальном окружении
        source venv/bin/activate
        python3 -c "import cv2, ultralytics, flask, numpy" || {
            print_error "Не все Python модули установлены"
            exit 1
        }
        print_success "Все Python модули установлены корректно"
    else
        print_error "Виртуальное окружение не найдено"
        exit 1
    fi
    
    print_success "Все зависимости установлены корректно"
}

# Основная функция
main() {
    print_header "DC-Detector - Полная установка"
    
    update_system
    install_system_dependencies
    setup_camera
    create_venv
    install_python_dependencies
    verify_installation
    
    print_header "Установка завершена!"
    print_success "Теперь запустите: ./start.sh"
    print_info "start.sh только запустит приложение (все уже установлено)"
}

main "$@"
