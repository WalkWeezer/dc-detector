#!/bin/bash

# 🚀 Quick Start Script для DC-Detector
# Быстрый запуск системы детекции огня

set -e

# Цвета
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}🔥 DC-Detector Quick Start${NC}"
    echo "=========================="
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Проверка установки
check_installation() {
    if [ ! -d "fire_detection_env" ]; then
        echo -e "${YELLOW}⚠️  Виртуальное окружение не найдено${NC}"
        echo "Запустите сначала: ./setup.sh"
        exit 1
    fi
    
    if [ ! -f "app_pi.py" ]; then
        echo -e "${YELLOW}⚠️  Файл app_pi.py не найден${NC}"
        echo "Убедитесь, что вы в правильной директории"
        exit 1
    fi
}

# Проверка камеры
check_camera() {
    if vcgencmd get_camera | grep -q "supported=1 detected=1"; then
        print_success "Камера готова к работе"
    else
        echo -e "${YELLOW}⚠️  Камера не обнаружена${NC}"
        echo "Проверьте подключение PiCamera"
    fi
}

# Запуск системы
start_system() {
    print_info "Запуск системы детекции огня..."
    
    source fire_detection_env/bin/activate
    python app_pi.py
}

# Главная функция
main() {
    print_header
    
    check_installation
    check_camera
    
    echo ""
    print_info "Нажмите Ctrl+C для остановки"
    echo ""
    
    start_system
}

# Обработка Ctrl+C
trap 'echo -e "\n${YELLOW}🛑 Остановка системы...${NC}"; exit 0' INT

# Запуск
main "$@"
