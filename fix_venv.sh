#!/bin/bash

# 🔥 DC-Detector - Исправление виртуального окружения
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

# Удаление проблемного виртуального окружения
clean_venv() {
    print_info "Очистка проблемного виртуального окружения..."
    
    if [ -d "venv" ]; then
        print_info "Удаление существующего виртуального окружения..."
        rm -rf venv
        print_success "Виртуальное окружение удалено"
    else
        print_info "Виртуальное окружение не найдено"
    fi
}

# Создание нового виртуального окружения
create_clean_venv() {
    print_info "Создание нового виртуального окружения..."
    
    # Создание виртуального окружения
    python3 -m venv venv
    
    if [ -d "venv" ]; then
        print_success "Виртуальное окружение создано"
    else
        print_error "Не удалось создать виртуальное окружение"
        exit 1
    fi
}

# Установка Python зависимостей
install_dependencies() {
    print_info "Установка Python зависимостей..."
    
    # Активация виртуального окружения
    source venv/bin/activate
    
    # Обновление pip
    print_info "Обновление pip..."
    pip install --upgrade pip
    
    # Установка зависимостей из исправленного requirements.txt
    if [ -f "requirements.txt" ]; then
        print_info "Установка зависимостей из requirements.txt..."
        pip install -r requirements.txt
    else
        print_info "Установка основных зависимостей..."
        pip install opencv-python ultralytics flask numpy pillow picamera2
    fi
    
    print_success "Python зависимости установлены"
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
        print_info "Попробуйте установить вручную:"
        echo "source venv/bin/activate"
        echo "pip install ${missing_modules[*]}"
        return 1
    fi
    
    print_success "Все модули установлены корректно"
}

# Основная функция
main() {
    print_header "DC-Detector - Исправление виртуального окружения"
    
    clean_venv
    create_clean_venv
    install_dependencies
    verify_installation
    
    print_header "Исправление завершено!"
    print_success "Теперь запустите: ./start.sh"
}

main "$@"
