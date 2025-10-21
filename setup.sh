#!/bin/bash

# 🔥 DC-Detector Auto Setup Script для Raspberry Pi
# Автоматическая установка и настройка системы детекции огня
# Версия: 1.0

set -e  # Остановка при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для красивого вывода
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

# Проверка, что мы на Raspberry Pi
check_raspberry_pi() {
    if ! grep -q "Raspberry Pi" /proc/cpuinfo; then
        print_warning "Этот скрипт предназначен для Raspberry Pi"
        read -p "Продолжить установку? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Обновление системы
update_system() {
    print_header "Обновление системы"
    print_info "Обновление пакетов..."
    sudo apt update && sudo apt upgrade -y
    print_success "Система обновлена"
}

# Установка системных зависимостей
install_system_dependencies() {
    print_header "Установка системных зависимостей"
    
    print_info "Установка основных пакетов..."
    sudo apt install -y \
        python3-pip \
        python3-venv \
        python3-dev \
        python3-opencv \
        libopencv-dev \
        libhdf5-dev \
        libhdf5-serial-dev \
        libatlas-base-dev \
        libjasper-dev \
        libqtgui4 \
        libqt4-test \
        libqt4-dev \
        libqt4-opengl-dev \
        libavcodec-dev \
        libavformat-dev \
        libswscale-dev \
        libv4l-dev \
        libxvidcore-dev \
        libx264-dev \
        libgtk-3-dev \
        libtbb2 \
        libtbb-dev \
        libdc1394-dev \
        v4l-utils \
        git \
        wget \
        curl \
        build-essential \
        cmake \
        pkg-config
    
    print_info "Установка зависимостей для камеры..."
    sudo apt install -y \
        libcap-dev \
        libcap2-dev \
        libcap-ng-dev \
        libcap-ng0 \
        libcamera-dev \
        libcamera-tools \
        python3-libcamera \
        python3-kms++ \
        python3-pyqt5 \
        python3-pyqt5.qtwidgets \
        qtbase5-dev \
        libqt5core5a \
        libqt5gui5 \
        libqt5widgets5 \
        libqt5test5 \
        libqt5concurrent5 \
        libqt5opengl5-dev \
        libqt5opengl5 \
        libgl1-mesa-dev \
        libglu1-mesa-dev \
        libdrm-dev \
        libxkbcommon-dev \
        libxkbcommon-x11-dev \
        libxcb-randr0-dev \
        libxcb-xtest0-dev \
        libxcb-shape0-dev \
        libxcb-xfixes0-dev \
        libxcb-util-dev \
        libxcb-keysyms1-dev \
        libxcb-icccm4-dev \
        libxcb-cursor-dev \
        libxcb-xinerama0-dev \
        libxcb-xkb-dev \
        libxcb-image0-dev \
        libxcb-xrm-dev \
        libxcb-util0-dev
    
    print_success "Системные зависимости установлены"
}

# Настройка камеры
setup_camera() {
    print_header "Настройка камеры"
    
    print_info "Включение камеры..."
    sudo raspi-config nonint do_camera 0
    
    print_info "Проверка камеры..."
    if vcgencmd get_camera | grep -q "supported=1 detected=1"; then
        print_success "Камера обнаружена и готова к работе"
    else
        print_warning "Камера не обнаружена. Убедитесь, что она подключена."
    fi
}

# Создание виртуального окружения
create_venv() {
    print_header "Создание виртуального окружения"
    
    print_info "Создание виртуального окружения..."
    python3 -m venv fire_detection_env
    source fire_detection_env/bin/activate
    
    print_info "Обновление pip..."
    pip install --upgrade pip
    
    print_success "Виртуальное окружение создано"
}

# Установка Python зависимостей
install_python_dependencies() {
    print_header "Установка Python зависимостей"
    
    source fire_detection_env/bin/activate
    
    print_info "Установка PyTorch для ARM..."
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
    
    print_info "Установка основных зависимостей..."
    pip install ultralytics==8.0.196
    pip install opencv-python-headless==4.8.1.78
    pip install flask==2.3.3
    pip install numpy==1.24.3
    pip install pillow==10.0.1
    pip install psutil==5.9.5
    pip install picamera2==0.3.12
    pip install gpiozero==1.6.2
    
    print_success "Python зависимости установлены"
}

# Создание директорий и файлов
create_directories() {
    print_header "Создание директорий"
    
    mkdir -p logs
    mkdir -p recordings
    mkdir -p models
    
    print_success "Директории созданы"
}

# Настройка systemd сервиса
setup_systemd() {
    print_header "Настройка автозапуска"
    
    print_info "Создание systemd сервиса..."
    sudo tee /etc/systemd/system/fire-detection.service > /dev/null <<EOF
[Unit]
Description=Fire Detection System
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/fire_detection_env/bin
ExecStart=$(pwd)/fire_detection_env/bin/python app_pi.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    print_success "Systemd сервис настроен"
}

# Создание скриптов управления
create_management_scripts() {
    print_header "Создание скриптов управления"
    
    # Скрипт запуска
    cat > start_fire_detection.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source fire_detection_env/bin/activate
python app_pi.py
EOF

    # Скрипт остановки
    cat > stop_fire_detection.sh << 'EOF'
#!/bin/bash
sudo systemctl stop fire-detection
EOF

    # Скрипт статуса
    cat > status_fire_detection.sh << 'EOF'
#!/bin/bash
sudo systemctl status fire-detection
EOF

    # Скрипт перезапуска
    cat > restart_fire_detection.sh << 'EOF'
#!/bin/bash
sudo systemctl restart fire-detection
EOF

    # Скрипт логов
    cat > logs_fire_detection.sh << 'EOF'
#!/bin/bash
journalctl -u fire-detection -f
EOF

    chmod +x *.sh
    print_success "Скрипты управления созданы"
}

# Настройка прав доступа
setup_permissions() {
    print_header "Настройка прав доступа"
    
    chmod +x *.sh
    chown -R pi:pi .
    
    # Добавление пользователя в группу video
    sudo usermod -a -G video $USER
    
    print_success "Права доступа настроены"
}

# Финальная проверка
final_check() {
    print_header "Финальная проверка"
    
    source fire_detection_env/bin/activate
    
    print_info "Проверка импортов..."
    python -c "
import cv2
import ultralytics
import numpy as np
import flask
import psutil
print('✅ Все основные модули работают')
" 2>/dev/null && print_success "Все модули импортированы успешно" || print_error "Ошибка импорта модулей"
    
    print_info "Проверка камеры..."
    if vcgencmd get_camera | grep -q "supported=1 detected=1"; then
        print_success "Камера готова к работе"
    else
        print_warning "Камера не обнаружена"
    fi
}

# Получение IP адреса
get_ip_address() {
    IP_ADDRESS=$(hostname -I | awk '{print $1}')
    echo "$IP_ADDRESS"
}

# Вывод информации о завершении
show_completion_info() {
    print_header "Установка завершена!"
    
    IP_ADDRESS=$(get_ip_address)
    
    echo -e "${GREEN}🎉 Система детекции огня готова к работе!${NC}"
    echo ""
    echo -e "${BLUE}🌐 Веб-интерфейс доступен по адресу:${NC}"
    echo -e "   http://$IP_ADDRESS:5000"
    echo -e "   http://localhost:5000"
    echo ""
    echo -e "${BLUE}🚀 Команды для управления:${NC}"
    echo -e "   ${YELLOW}Запуск:${NC}     ./start_fire_detection.sh"
    echo -e "   ${YELLOW}Остановка:${NC}  ./stop_fire_detection.sh"
    echo -e "   ${YELLOW}Статус:${NC}     ./status_fire_detection.sh"
    echo -e "   ${YELLOW}Логи:${NC}       ./logs_fire_detection.sh"
    echo -e "   ${YELLOW}Перезапуск:${NC} ./restart_fire_detection.sh"
    echo ""
    echo -e "${BLUE}📋 Следующие шаги:${NC}"
    echo -e "1. Убедитесь, что PiCamera подключена"
    echo -e "2. Запустите систему: ${GREEN}./start_fire_detection.sh${NC}"
    echo -e "3. Откройте браузер и перейдите по адресу выше"
    echo ""
    echo -e "${YELLOW}⚠️  Важно: Перезагрузите Raspberry Pi для активации камеры!${NC}"
    echo -e "   ${YELLOW}sudo reboot${NC}"
    echo ""
}

# Главная функция
main() {
    print_header "DC-Detector Auto Setup"
    print_info "Автоматическая установка системы детекции огня для Raspberry Pi"
    echo ""
    
    check_raspberry_pi
    update_system
    install_system_dependencies
    setup_camera
    create_venv
    install_python_dependencies
    create_directories
    setup_systemd
    create_management_scripts
    setup_permissions
    final_check
    show_completion_info
    
    # Спрашиваем о перезагрузке
    echo ""
    read -p "Перезагрузить Raspberry Pi сейчас? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Перезагрузка через 5 секунд..."
        sleep 5
        sudo reboot
    else
        print_warning "Не забудьте перезагрузить систему для активации камеры!"
    fi
}

# Запуск главной функции
main "$@"
