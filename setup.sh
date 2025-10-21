#!/bin/bash

# 🔥 DC-Detector Setup для Raspberry Pi
# Скрипт установки с логированием
# Версия: 1.0

set -e

# Настройка логирования
LOG_FILE="setup_log_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE")
exec 2>&1

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
    echo "=== $1 ===" >> "$LOG_FILE"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
    echo "SUCCESS: $1" >> "$LOG_FILE"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    echo "WARNING: $1" >> "$LOG_FILE"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    echo "ERROR: $1" >> "$LOG_FILE"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
    echo "INFO: $1" >> "$LOG_FILE"
}

# Функция для логирования команд
log_command() {
    echo "EXECUTING: $1" >> "$LOG_FILE"
    echo "Command: $1" >> "$LOG_FILE"
}

# Проверка системы
check_system() {
    print_header "Проверка системы"
    
    echo "System info:" >> "$LOG_FILE"
    uname -a >> "$LOG_FILE"
    cat /proc/cpuinfo | grep Model >> "$LOG_FILE"
    cat /proc/version >> "$LOG_FILE"
    
    if ! grep -q "Raspberry Pi" /proc/cpuinfo; then
        print_warning "Этот скрипт предназначен для Raspberry Pi"
        read -p "Продолжить установку? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_error "Установка отменена пользователем"
            exit 1
        fi
    fi
    
    print_success "Система проверена"
}

# Удаление проблемного GitHub CLI репозитория
remove_github_cli_repo() {
    print_info "Проверка и удаление проблемного GitHub CLI репозитория..."
    
    if [ -f "/etc/apt/sources.list.d/github-cli.list" ]; then
        print_info "Удаление GitHub CLI репозитория..."
        log_command "sudo rm /etc/apt/sources.list.d/github-cli.list"
        sudo rm /etc/apt/sources.list.d/github-cli.list 2>&1 | tee -a "$LOG_FILE"
        print_success "GitHub CLI репозиторий удален"
    else
        print_info "GitHub CLI репозиторий не найден"
    fi
}

# Обновление системы
update_system() {
    print_header "Обновление системы"
    
    # Сначала удаляем проблемный репозиторий
    remove_github_cli_repo
    
    print_info "Обновление пакетов..."
    
    log_command "sudo apt update"
    sudo apt update 2>&1 | tee -a "$LOG_FILE"
    
    # Проверяем результат обновления
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "Система обновлена"
    else
        # Проверяем, есть ли только GitHub CLI ошибки
        if grep -q "cli.github.com" "$LOG_FILE" && ! grep -q "E: " "$LOG_FILE" | grep -v "cli.github.com"; then
            print_warning "GitHub CLI репозиторий недоступен, но это не критично"
            print_success "Система обновлена (игнорируя GitHub CLI ошибки)"
        else
            print_error "Ошибка обновления системы"
            echo "APT UPDATE FAILED" >> "$LOG_FILE"
            exit 1
        fi
    fi
}

# Установка только самых необходимых пакетов
install_essential() {
    print_header "Установка необходимых пакетов"
    
    print_info "Установка основных пакетов..."
    
    PACKAGES="python3-pip python3-venv python3-dev python3-opencv libopencv-dev libhdf5-dev libhdf5-serial-dev libatlas-base-dev libavcodec-dev libavformat-dev libswscale-dev libv4l-dev libxvidcore-dev libx264-dev libgtk-3-dev libdc1394-dev v4l-utils git wget curl build-essential cmake pkg-config libjpeg-dev libpng-dev libtiff-dev libwebp-dev libopenexr-dev"
    
    log_command "sudo apt install -y $PACKAGES"
    sudo apt install -y $PACKAGES 2>&1 | tee -a "$LOG_FILE"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "Основные пакеты установлены"
    else
        # Проверяем, есть ли только несущественные ошибки
        if grep -q "Unable to locate package" "$LOG_FILE" && ! grep -q "python3-pip\|python3-venv\|python3-dev" "$LOG_FILE"; then
            print_warning "Некоторые пакеты недоступны, но основные установлены"
            print_success "Основные пакеты установлены (с предупреждениями)"
        else
            print_error "Ошибка установки основных пакетов"
            echo "ESSENTIAL PACKAGES INSTALLATION FAILED" >> "$LOG_FILE"
            exit 1
        fi
    fi
}

# Установка GStreamer
install_gstreamer() {
    print_header "Установка GStreamer"
    
    print_info "Установка GStreamer..."
    
    GSTREAMER_PACKAGES="libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav gstreamer1.0-tools gstreamer1.0-x gstreamer1.0-alsa gstreamer1.0-gl gstreamer1.0-gtk3 gstreamer1.0-qt5 gstreamer1.0-pulseaudio"
    
    log_command "sudo apt install -y $GSTREAMER_PACKAGES"
    sudo apt install -y $GSTREAMER_PACKAGES 2>&1 | tee -a "$LOG_FILE"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "GStreamer установлен"
    else
        print_error "Ошибка установки GStreamer"
        echo "GSTREAMER INSTALLATION FAILED" >> "$LOG_FILE"
        exit 1
    fi
}

# Установка минимальных зависимостей для камеры
install_camera_dependencies() {
    print_header "Установка зависимостей для камеры"
    
    print_info "Установка минимальных зависимостей для PiCamera..."
    
    CAMERA_PACKAGES="libcap-dev libcap2-dev libcap-ng-dev libcap-ng0 libcamera-dev libcamera-tools python3-libcamera python3-kms++ libgl1-mesa-dev libglu1-mesa-dev libdrm-dev"
    
    log_command "sudo apt install -y $CAMERA_PACKAGES"
    sudo apt install -y $CAMERA_PACKAGES 2>&1 | tee -a "$LOG_FILE"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "Зависимости для камеры установлены"
    else
        print_error "Ошибка установки зависимостей для камеры"
        echo "CAMERA DEPENDENCIES INSTALLATION FAILED" >> "$LOG_FILE"
        exit 1
    fi
}

# Настройка камеры
setup_camera() {
    print_header "Настройка камеры"
    
    print_info "Включение камеры..."
    log_command "sudo raspi-config nonint do_camera 0"
    sudo raspi-config nonint do_camera 0 2>&1 | tee -a "$LOG_FILE"
    
    print_info "Проверка камеры..."
    log_command "vcgencmd get_camera"
    CAMERA_STATUS=$(vcgencmd get_camera 2>&1 | tee -a "$LOG_FILE")
    echo "Camera status: $CAMERA_STATUS" >> "$LOG_FILE"
    
    if echo "$CAMERA_STATUS" | grep -q "supported=1 detected=1"; then
        print_success "Камера обнаружена и готова к работе"
    else
        print_warning "Камера не обнаружена. Убедитесь, что она подключена."
        echo "CAMERA NOT DETECTED" >> "$LOG_FILE"
    fi
}

# Создание виртуального окружения
create_venv() {
    print_header "Создание виртуального окружения"
    
    print_info "Создание виртуального окружения..."
    log_command "python3 -m venv fire_detection_env"
    python3 -m venv fire_detection_env 2>&1 | tee -a "$LOG_FILE"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "Виртуальное окружение создано"
    else
        print_error "Ошибка создания виртуального окружения"
        echo "VENV CREATION FAILED" >> "$LOG_FILE"
        exit 1
    fi
    
    print_info "Активация виртуального окружения..."
    source fire_detection_env/bin/activate 2>&1 | tee -a "$LOG_FILE"
    
    print_info "Обновление pip..."
    log_command "fire_detection_env/bin/pip install --upgrade pip"
    fire_detection_env/bin/pip install --upgrade pip 2>&1 | tee -a "$LOG_FILE"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "Pip обновлен"
    else
        print_error "Ошибка обновления pip"
        echo "PIP UPDATE FAILED" >> "$LOG_FILE"
        exit 1
    fi
}

# Установка Python зависимостей
install_python_dependencies() {
    print_header "Установка Python зависимостей"
    
    print_info "Установка PyTorch для ARM..."
    log_command "fire_detection_env/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu"
    fire_detection_env/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu 2>&1 | tee -a "$LOG_FILE"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "PyTorch установлен"
    else
        print_error "Ошибка установки PyTorch"
        echo "PYTORCH INSTALLATION FAILED" >> "$LOG_FILE"
        exit 1
    fi
    
    print_info "Установка основных зависимостей..."
    PYTHON_PACKAGES="ultralytics==8.0.196 opencv-python-headless==4.8.1.78 flask==2.3.3 numpy==1.24.3 pillow==10.0.1 psutil==5.9.5"
    
    log_command "fire_detection_env/bin/pip install $PYTHON_PACKAGES"
    fire_detection_env/bin/pip install $PYTHON_PACKAGES 2>&1 | tee -a "$LOG_FILE"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "Основные Python зависимости установлены"
    else
        print_error "Ошибка установки основных Python зависимостей"
        echo "PYTHON PACKAGES INSTALLATION FAILED" >> "$LOG_FILE"
        exit 1
    fi
    
    print_info "Установка picamera2..."
    log_command "fire_detection_env/bin/pip install picamera2==0.3.12"
    fire_detection_env/bin/pip install picamera2==0.3.12 2>&1 | tee -a "$LOG_FILE"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "Picamera2 установлен"
    else
        print_error "Ошибка установки picamera2"
        echo "PICAMERA2 INSTALLATION FAILED" >> "$LOG_FILE"
        exit 1
    fi
    
    print_info "Установка дополнительных зависимостей..."
    log_command "fire_detection_env/bin/pip install gpiozero==1.6.2"
    fire_detection_env/bin/pip install gpiozero==1.6.2 2>&1 | tee -a "$LOG_FILE"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "Дополнительные зависимости установлены"
    else
        print_error "Ошибка установки дополнительных зависимостей"
        echo "ADDITIONAL PACKAGES INSTALLATION FAILED" >> "$LOG_FILE"
        exit 1
    fi
    
    print_success "Python зависимости установлены"
}

# Создание директорий
create_directories() {
    print_header "Создание директорий"
    
    log_command "mkdir -p logs recordings models"
    mkdir -p logs recordings models 2>&1 | tee -a "$LOG_FILE"
    
    print_success "Директории созданы"
}

# Настройка systemd сервиса
setup_systemd() {
    print_header "Настройка автозапуска"
    
    print_info "Создание systemd сервиса..."
    log_command "Creating systemd service"
    
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

    log_command "sudo systemctl daemon-reload"
    sudo systemctl daemon-reload 2>&1 | tee -a "$LOG_FILE"
    
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

    log_command "chmod +x *.sh"
    chmod +x *.sh 2>&1 | tee -a "$LOG_FILE"
    
    print_success "Скрипты управления созданы"
}

# Настройка прав доступа
setup_permissions() {
    print_header "Настройка прав доступа"
    
    log_command "chmod +x *.sh && chown -R pi:pi ."
    chmod +x *.sh 2>&1 | tee -a "$LOG_FILE"
    chown -R pi:pi . 2>&1 | tee -a "$LOG_FILE"
    
    # Добавление пользователя в группу video
    log_command "sudo usermod -a -G video $USER"
    sudo usermod -a -G video $USER 2>&1 | tee -a "$LOG_FILE"
    
    print_success "Права доступа настроены"
}

# Финальная проверка
final_check() {
    print_header "Финальная проверка"
    
    print_info "Проверка импортов..."
    log_command "fire_detection_env/bin/python -c 'import cv2, ultralytics, numpy, flask, psutil'"
    fire_detection_env/bin/python -c "
import cv2
import ultralytics
import numpy as np
import flask
import psutil
print('✅ Все основные модули работают')
" 2>&1 | tee -a "$LOG_FILE"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "Все модули импортированы успешно"
    else
        print_error "Ошибка импорта модулей"
        echo "MODULE IMPORT FAILED" >> "$LOG_FILE"
    fi
    
    print_info "Проверка камеры..."
    log_command "vcgencmd get_camera"
    CAMERA_CHECK=$(vcgencmd get_camera 2>&1 | tee -a "$LOG_FILE")
    
    if echo "$CAMERA_CHECK" | grep -q "supported=1 detected=1"; then
        print_success "Камера готова к работе"
    else
        print_warning "Камера не обнаружена"
        echo "CAMERA NOT READY" >> "$LOG_FILE"
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
    echo -e "${BLUE}📄 Лог установки сохранен в: $LOG_FILE${NC}"
    echo ""
    
    # Автоматический коммит логов
    if [ -f "commit_logs.sh" ]; then
        print_info "Автоматический коммит логов..."
        chmod +x commit_logs.sh
        ./commit_logs.sh
    fi
}

# Обработка ошибок
trap 'print_error "Установка прервана на этапе: $BASH_COMMAND"; echo "INSTALLATION INTERRUPTED at: $BASH_COMMAND" >> "$LOG_FILE"; exit 1' ERR

# Главная функция
main() {
    print_header "DC-Detector Setup"
    print_info "Установка системы детекции огня для Raspberry Pi"
    print_info "Лог установки: $LOG_FILE"
    echo ""
    
    check_system
    update_system
    install_essential
    install_gstreamer
    install_camera_dependencies
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