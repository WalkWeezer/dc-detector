#!/bin/bash

# 🔍 DC-Detector Dependencies Checker
# Проверка всех зависимостей без установки

set -e

# Цвета
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}🔍 $1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Проверка системы
check_system() {
    print_header "Проверка системы"
    
    print_info "Информация о системе:"
    echo "  ОС: $(lsb_release -d | cut -f2)"
    echo "  Архитектура: $(uname -m)"
    echo "  Python: $(python3 --version)"
    echo "  Pip: $(python3 -m pip --version | cut -d' ' -f2)"
    
    if grep -q "Raspberry Pi" /proc/cpuinfo; then
        print_success "Raspberry Pi обнаружен"
        echo "  Модель: $(cat /proc/cpuinfo | grep Model | cut -d: -f2 | xargs)"
    else
        print_warning "Это не Raspberry Pi"
    fi
    echo ""
}

# Проверка системных пакетов
check_system_packages() {
    print_header "Проверка системных пакетов"
    
    print_info "Проверка основных пакетов..."
    
    PACKAGES=("python3-pip" "python3-venv" "python3-dev" "python3-opencv" "libopencv-dev" "build-essential" "cmake" "pkg-config" "git" "wget" "curl")
    
    for package in "${PACKAGES[@]}"; do
        if dpkg -l | grep -q "^ii.*$package"; then
            print_success "$package установлен"
        else
            print_error "$package не установлен"
        fi
    done
    
    print_info "Проверка пакетов для компьютерного зрения..."
    
    CV_PACKAGES=("libhdf5-dev" "libatlas-base-dev" "libavcodec-dev" "libavformat-dev" "libswscale-dev" "libv4l-dev" "libxvidcore-dev" "libx264-dev" "libgtk-3-dev")
    
    for package in "${CV_PACKAGES[@]}"; do
        if dpkg -l | grep -q "^ii.*$package"; then
            print_success "$package установлен"
        else
            print_warning "$package не установлен"
        fi
    done
    
    print_info "Проверка пакетов для изображений..."
    
    IMAGE_PACKAGES=("libjpeg-dev" "libpng-dev" "libtiff-dev" "libwebp-dev")
    
    for package in "${IMAGE_PACKAGES[@]}"; do
        if dpkg -l | grep -q "^ii.*$package"; then
            print_success "$package установлен"
        else
            print_warning "$package не установлен"
        fi
    done
    
    print_info "Проверка пакетов для камеры..."
    
    CAMERA_PACKAGES=("libcamera-tools" "libcamera-dev" "python3-libcamera" "v4l-utils")
    
    for package in "${CAMERA_PACKAGES[@]}"; do
        if dpkg -l | grep -q "^ii.*$package"; then
            print_success "$package установлен"
        else
            print_warning "$package не установлен"
        fi
    done
    
    echo ""
}

# Проверка виртуального окружения
check_virtual_environment() {
    print_header "Проверка виртуального окружения"
    
    if [ -d "fire_detection_env" ]; then
        print_success "Виртуальное окружение найдено"
        
        print_info "Активация виртуального окружения..."
        source fire_detection_env/bin/activate
        
        print_info "Проверка pip в виртуальном окружении..."
        pip --version
        
    else
        print_error "Виртуальное окружение не найдено"
        print_info "Создайте его командой: python3 -m venv fire_detection_env"
    fi
    echo ""
}

# Проверка Python модулей
check_python_modules() {
    print_header "Проверка Python модулей"
    
    if [ -d "fire_detection_env" ]; then
        source fire_detection_env/bin/activate
        
        print_info "Проверка основных модулей..."
        
        MODULES=("cv2" "ultralytics" "flask" "numpy" "PIL" "picamera2" "psutil" "gpiozero")
        
        for module in "${MODULES[@]}"; do
            if python3 -c "import $module" 2>/dev/null; then
                print_success "$module импортируется корректно"
            else
                print_error "$module не может быть импортирован"
            fi
        done
        
        echo ""
        print_info "Проверка версий модулей..."
        python3 -c "
try:
    import cv2
    print(f'✅ OpenCV: {cv2.__version__}')
except ImportError:
    print('❌ OpenCV не установлен')

try:
    import ultralytics
    print(f'✅ Ultralytics: {ultralytics.__version__}')
except ImportError:
    print('❌ Ultralytics не установлен')

try:
    import flask
    print(f'✅ Flask: {flask.__version__}')
except ImportError:
    print('❌ Flask не установлен')

try:
    import numpy
    print(f'✅ NumPy: {numpy.__version__}')
except ImportError:
    print('❌ NumPy не установлен')

try:
    import PIL
    print(f'✅ Pillow: {PIL.__version__}')
except ImportError:
    print('❌ Pillow не установлен')

try:
    import psutil
    print(f'✅ Psutil: {psutil.__version__}')
except ImportError:
    print('❌ Psutil не установлен')
"
        
    else
        print_error "Виртуальное окружение не найдено, проверка модулей невозможна"
    fi
    echo ""
}

# Проверка файлов проекта
check_project_files() {
    print_header "Проверка файлов проекта"
    
    PROJECT_FILES=("app_pi.py" "config_pi.py" "bestfire.pt" "requirements.txt" "README.md")
    
    for file in "${PROJECT_FILES[@]}"; do
        if [ -f "$file" ]; then
            print_success "$file найден"
        else
            print_error "$file не найден"
        fi
    done
    
    echo ""
}

# Проверка камеры
check_camera() {
    print_header "Проверка камеры"
    
    print_info "Проверка статуса камеры..."
    if command -v vcgencmd >/dev/null 2>&1; then
        CAMERA_STATUS=$(vcgencmd get_camera 2>/dev/null || echo "error")
        echo "Статус камеры: $CAMERA_STATUS"
        
        if echo "$CAMERA_STATUS" | grep -q "supported=1 detected=1"; then
            print_success "Камера обнаружена и готова"
        elif echo "$CAMERA_STATUS" | grep -q "supported=1 detected=0"; then
            print_warning "Камера поддерживается, но не обнаружена"
        else
            print_error "Проблемы с камерой"
        fi
    else
        print_error "vcgencmd недоступен"
    fi
    
    print_info "Проверка libcamera..."
    if command -v libcamera-hello >/dev/null 2>&1; then
        print_success "libcamera-hello доступен"
    elif command -v libcamera-still >/dev/null 2>&1; then
        print_success "libcamera-still доступен"
    else
        print_warning "libcamera команды не найдены"
    fi
    
    echo ""
}

# Рекомендации
show_recommendations() {
    print_header "Рекомендации"
    
    print_info "Если обнаружены проблемы:"
    echo ""
    echo "1. Установите недостающие зависимости:"
    echo "   ./install_dependencies.sh"
    echo ""
    echo "2. Обновите систему:"
    echo "   sudo apt update && sudo apt upgrade"
    echo ""
    echo "3. Переустановите виртуальное окружение:"
    echo "   rm -rf fire_detection_env"
    echo "   python3 -m venv fire_detection_env"
    echo ""
    echo "4. Включите камеру:"
    echo "   sudo raspi-config"
    echo ""
}

# Главная функция
main() {
    print_header "DC-Detector Dependencies Checker"
    print_info "Проверка всех зависимостей для машинного зрения"
    echo ""
    
    check_system
    check_system_packages
    check_virtual_environment
    check_python_modules
    check_project_files
    check_camera
    show_recommendations
    
    print_header "Проверка завершена!"
    print_info "Все зависимости проверены"
    echo ""
}

# Запуск
main "$@"
