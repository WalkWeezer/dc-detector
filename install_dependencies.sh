#!/bin/bash

# 🔥 DC-Detector Dependencies Installer
# Установка и проверка всех зависимостей для машинного зрения

set -e

# Цвета
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}🔥 $1${NC}"
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
        print_warning "Это не Raspberry Pi, но установка продолжится"
    fi
    echo ""
}

# Обновление системы
update_system() {
    print_header "Обновление системы"
    
    print_info "Обновление списков пакетов..."
    sudo apt update -y
    
    print_info "Обновление системы..."
    sudo apt upgrade -y
    
    print_success "Система обновлена"
    echo ""
}

# Установка системных зависимостей
install_system_dependencies() {
    print_header "Установка системных зависимостей"
    
    print_info "Установка основных пакетов для машинного зрения..."
    
    # Основные пакеты
    SYSTEM_PACKAGES="python3-pip python3-venv python3-dev python3-opencv libopencv-dev"
    
    # Пакеты для компьютерного зрения
    CV_PACKAGES="libhdf5-dev libhdf5-serial-dev libatlas-base-dev libavcodec-dev libavformat-dev libswscale-dev libv4l-dev libxvidcore-dev libx264-dev libgtk-3-dev libdc1394-dev"
    
    # Пакеты для изображений
    IMAGE_PACKAGES="libjpeg-dev libpng-dev libtiff-dev libwebp-dev libopenexr-dev"
    
    # Пакеты для сборки
    BUILD_PACKAGES="build-essential cmake pkg-config git wget curl"
    
    # Пакеты для камеры
    CAMERA_PACKAGES="libcamera-tools libcamera-dev python3-libcamera v4l-utils"
    
    ALL_PACKAGES="$SYSTEM_PACKAGES $CV_PACKAGES $IMAGE_PACKAGES $BUILD_PACKAGES $CAMERA_PACKAGES"
    
    print_info "Установка пакетов: $ALL_PACKAGES"
    sudo apt install -y $ALL_PACKAGES
    
    print_success "Системные зависимости установлены"
    echo ""
}

# Создание виртуального окружения
create_virtual_environment() {
    print_header "Создание виртуального окружения"
    
    if [ -d "fire_detection_env" ]; then
        print_warning "Виртуальное окружение уже существует"
        read -p "Пересоздать? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Удаление старого окружения..."
            rm -rf fire_detection_env
        else
            print_info "Используем существующее окружение"
            return
        fi
    fi
    
    print_info "Создание виртуального окружения..."
    python3 -m venv fire_detection_env
    
    print_info "Активация виртуального окружения..."
    source fire_detection_env/bin/activate
    
    print_info "Обновление pip..."
    pip install --upgrade pip
    
    print_success "Виртуальное окружение создано"
    echo ""
}

# Установка Python зависимостей
install_python_dependencies() {
    print_header "Установка Python зависимостей"
    
    print_info "Активация виртуального окружения..."
    source fire_detection_env/bin/activate
    
    print_info "Установка PyTorch для ARM..."
    pip install torch==2.0.1 torchvision==0.15.2 --index-url https://download.pytorch.org/whl/cpu
    
    print_info "Установка основных зависимостей..."
    pip install ultralytics==8.0.196
    pip install opencv-python==4.8.1.78
    pip install flask==2.3.3
    pip install numpy==1.24.3
    pip install pillow==10.0.1
    
    print_info "Установка зависимостей для камеры..."
    pip install picamera2==0.3.12
    
    print_info "Установка дополнительных утилит..."
    pip install psutil==5.9.5
    pip install gpiozero==1.6.2
    
    print_success "Python зависимости установлены"
    echo ""
}

# Проверка установки
verify_installation() {
    print_header "Проверка установки"
    
    print_info "Активация виртуального окружения..."
    source fire_detection_env/bin/activate
    
    print_info "Проверка основных модулей..."
    
    # Проверка Python модулей
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
import cv2
import ultralytics
import flask
import numpy
import PIL
import psutil
print(f'OpenCV: {cv2.__version__}')
print(f'Ultralytics: {ultralytics.__version__}')
print(f'Flask: {flask.__version__}')
print(f'NumPy: {numpy.__version__}')
print(f'Pillow: {PIL.__version__}')
print(f'Psutil: {psutil.__version__}')
"
    
    print_success "Проверка завершена"
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
        else
            print_warning "Камера не обнаружена"
            print_info "Включите камеру: sudo raspi-config"
        fi
    else
        print_warning "vcgencmd недоступен"
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

# Создание скрипта запуска
create_launcher() {
    print_header "Создание скрипта запуска"
    
    cat > start_fire_detection.sh << 'EOF'
#!/bin/bash

# 🔥 DC-Detector Launcher
# Запуск системы детекции огня

echo "🔥 Запуск DC-Detector..."

# Проверка виртуального окружения
if [ ! -d "fire_detection_env" ]; then
    echo "❌ Виртуальное окружение не найдено"
    echo "Запустите: ./install_dependencies.sh"
    exit 1
fi

# Активация виртуального окружения
source fire_detection_env/bin/activate

# Проверка файлов
if [ ! -f "app_pi.py" ]; then
    echo "❌ app_pi.py не найден"
    exit 1
fi

if [ ! -f "bestfire.pt" ]; then
    echo "❌ bestfire.pt не найден"
    exit 1
fi

# Запуск приложения
echo "✅ Запуск системы детекции огня..."
python app_pi.py
EOF
    
    chmod +x start_fire_detection.sh
    
    print_success "Скрипт запуска создан: start_fire_detection.sh"
    echo ""
}

# Главная функция
main() {
    print_header "DC-Detector Dependencies Installer"
    print_info "Установка и проверка всех зависимостей для машинного зрения"
    echo ""
    
    check_system
    update_system
    install_system_dependencies
    create_virtual_environment
    install_python_dependencies
    verify_installation
    check_camera
    create_launcher
    
    print_header "Установка завершена!"
    print_success "Все зависимости установлены и проверены"
    echo ""
    print_info "Для запуска системы используйте:"
    echo "  ./start_fire_detection.sh"
    echo ""
    print_info "Или активируйте окружение вручную:"
    echo "  source fire_detection_env/bin/activate"
    echo "  python app_pi.py"
    echo ""
}

# Обработка ошибок
trap 'print_error "Установка прервана"; exit 1' INT TERM

# Запуск
main "$@"
