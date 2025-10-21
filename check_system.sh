#!/bin/bash

# 🔍 System Check Script для DC-Detector
# Проверка состояния системы детекции огня

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}🔍 DC-Detector System Check${NC}"
    echo "============================="
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
    print_info "Информация о системе:"
    echo "  Модель: $(cat /proc/cpuinfo | grep Model | cut -d: -f2 | xargs)"
    echo "  Архитектура: $(uname -m)"
    echo "  ОС: $(lsb_release -d | cut -f2)"
    echo "  Python: $(python3 --version)"
    echo ""
}

# Проверка камеры
check_camera() {
    print_info "Проверка камеры:"
    
    if vcgencmd get_camera | grep -q "supported=1 detected=1"; then
        print_success "Камера обнаружена и готова"
    else
        print_error "Камера не обнаружена"
        echo "  Проверьте подключение PiCamera"
        echo "  Включите камеру: sudo raspi-config"
    fi
    echo ""
}

# Проверка виртуального окружения
check_venv() {
    print_info "Проверка виртуального окружения:"
    
    if [ -d "fire_detection_env" ]; then
        print_success "Виртуальное окружение найдено"
        
        # Активируем и проверяем модули
        source fire_detection_env/bin/activate
        
        echo "  Проверка модулей:"
        python -c "import cv2; print('  ✅ OpenCV:', cv2.__version__)" 2>/dev/null || print_error "  ❌ OpenCV не установлен"
        python -c "import ultralytics; print('  ✅ Ultralytics:', ultralytics.__version__)" 2>/dev/null || print_error "  ❌ Ultralytics не установлен"
        python -c "import flask; print('  ✅ Flask:', flask.__version__)" 2>/dev/null || print_error "  ❌ Flask не установлен"
        python -c "import picamera2; print('  ✅ Picamera2 установлен')" 2>/dev/null || print_error "  ❌ Picamera2 не установлен"
        python -c "import psutil; print('  ✅ Psutil установлен')" 2>/dev/null || print_error "  ❌ Psutil не установлен"
    else
        print_error "Виртуальное окружение не найдено"
        echo "  Запустите: ./setup.sh"
    fi
    echo ""
}

# Проверка файлов проекта
check_files() {
    print_info "Проверка файлов проекта:"
    
    [ -f "app_pi.py" ] && print_success "app_pi.py найден" || print_error "app_pi.py не найден"
    [ -f "config_pi.py" ] && print_success "config_pi.py найден" || print_error "config_pi.py не найден"
    [ -f "bestfire.pt" ] && print_success "bestfire.pt найден" || print_error "bestfire.pt не найден"
    [ -f "requirements.txt" ] && print_success "requirements.txt найден" || print_error "requirements.txt не найден"
    echo ""
}

# Проверка systemd сервиса
check_service() {
    print_info "Проверка systemd сервиса:"
    
    if systemctl is-active --quiet fire-detection; then
        print_success "Сервис fire-detection запущен"
    elif systemctl is-enabled --quiet fire-detection; then
        print_warning "Сервис fire-detection включен, но не запущен"
    else
        print_warning "Сервис fire-detection не настроен"
    fi
    echo ""
}

# Проверка ресурсов
check_resources() {
    print_info "Проверка ресурсов системы:"
    
    # CPU температура
    temp=$(vcgencmd measure_temp | cut -d= -f2)
    echo "  Температура CPU: $temp"
    
    # Использование памяти
    memory=$(free -h | awk 'NR==2{printf "%.1f%%", $3*100/$2}')
    echo "  Использование памяти: $memory"
    
    # Свободное место
    disk=$(df -h . | awk 'NR==2{print $4}')
    echo "  Свободное место: $disk"
    
    # Загрузка системы
    load=$(uptime | awk -F'load average:' '{print $2}')
    echo "  Загрузка системы:$load"
    echo ""
}

# Проверка сети
check_network() {
    print_info "Проверка сети:"
    
    ip=$(hostname -I | awk '{print $1}')
    echo "  IP адрес: $ip"
    
    if ping -c 1 8.8.8.8 >/dev/null 2>&1; then
        print_success "Интернет соединение работает"
    else
        print_warning "Проблемы с интернет соединением"
    fi
    echo ""
}

# Рекомендации
show_recommendations() {
    print_info "Рекомендации:"
    
    # Проверяем температуру
    temp_num=$(vcgencmd measure_temp | cut -d= -f2 | cut -d\' -f1)
    if (( $(echo "$temp_num > 70" | bc -l) )); then
        print_warning "Высокая температура CPU ($temp_num°C)"
        echo "  Рекомендуется добавить охлаждение"
    fi
    
    # Проверяем свободное место
    free_space=$(df . | awk 'NR==2{print $4}')
    if [ "$free_space" -lt 1000000 ]; then  # Меньше 1GB
        print_warning "Мало свободного места ($(df -h . | awk 'NR==2{print $4}'))"
        echo "  Рекомендуется освободить место"
    fi
    
    echo ""
}

# Главная функция
main() {
    print_header
    echo ""
    
    check_system
    check_camera
    check_venv
    check_files
    check_service
    check_resources
    check_network
    show_recommendations
    
    echo -e "${GREEN}🎯 Проверка завершена!${NC}"
    echo ""
    echo "Для запуска системы используйте:"
    echo "  ./quick_start.sh"
    echo ""
    echo "Для управления сервисом:"
    echo "  sudo systemctl start fire-detection"
    echo "  sudo systemctl stop fire-detection"
    echo "  sudo systemctl status fire-detection"
}

# Запуск
main "$@"
