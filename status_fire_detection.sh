#!/bin/bash

# 🔥 DC-Detector - Скрипт проверки статуса системы детекции огня
# Автор: DC-Detector Team
# Версия: 1.0

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для вывода
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

# Проверка процессов
check_processes() {
    print_info "Проверка процессов DC-Detector..."
    
    local pids=$(pgrep -f "python.*app_pi.py" 2>/dev/null || true)
    
    if [ -n "$pids" ]; then
        print_success "DC-Detector запущен (PID: $pids)"
        
        # Дополнительная информация о процессах
        for pid in $pids; do
            local cmd=$(ps -p "$pid" -o cmd= 2>/dev/null || echo "N/A")
            local cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null || echo "N/A")
            local mem=$(ps -p "$pid" -o %mem= 2>/dev/null || echo "N/A")
            print_info "  PID $pid: CPU ${cpu}%, MEM ${mem}%"
            print_info "  Команда: $cmd"
        done
    else
        print_warning "DC-Detector не запущен"
    fi
}

# Проверка systemd сервиса
check_systemd() {
    print_info "Проверка systemd сервиса..."
    
    if command -v systemctl >/dev/null 2>&1; then
        local status=$(systemctl is-active fire-detection 2>/dev/null || echo "inactive")
        local enabled=$(systemctl is-enabled fire-detection 2>/dev/null || echo "disabled")
        
        if [ "$status" = "active" ]; then
            print_success "Systemd сервис активен"
        else
            print_warning "Systemd сервис неактивен (статус: $status)"
        fi
        
        if [ "$enabled" = "enabled" ]; then
            print_success "Systemd сервис включен для автозапуска"
        else
            print_warning "Systemd сервис отключен от автозапуска"
        fi
        
        # Показать последние логи
        print_info "Последние записи в логах systemd:"
        journalctl -u fire-detection --no-pager -n 5 2>/dev/null || print_warning "Логи systemd недоступны"
    else
        print_warning "Systemctl не найден"
    fi
}

# Проверка портов
check_ports() {
    print_info "Проверка сетевых портов..."
    
    local port=5000
    local pid=$(lsof -ti:$port 2>/dev/null || true)
    
    if [ -n "$pid" ]; then
        print_success "Порт $port занят процессом $pid"
        
        # Проверка доступности через curl
        if command -v curl >/dev/null 2>&1; then
            if curl -s -o /dev/null -w "%{http_code}" http://localhost:$port 2>/dev/null | grep -q "200"; then
                print_success "Веб-интерфейс доступен на http://localhost:$port"
            else
                print_warning "Порт $port открыт, но веб-интерфейс недоступен"
            fi
        fi
    else
        print_warning "Порт $port свободен"
    fi
}

# Проверка файлов
check_files() {
    print_info "Проверка файлов проекта..."
    
    local files=("app_pi.py" "config_pi.py" "bestfire.pt" "requirements.txt")
    local missing_files=()
    
    for file in "${files[@]}"; do
        if [ -f "$file" ]; then
            print_success "Файл $file найден"
        else
            print_error "Файл $file отсутствует"
            missing_files+=("$file")
        fi
    done
    
    if [ ${#missing_files[@]} -ne 0 ]; then
        print_error "Отсутствуют файлы: ${missing_files[*]}"
    fi
}

# Проверка виртуального окружения
check_venv() {
    print_info "Проверка виртуального окружения..."
    
    if [ -d "fire_detection_env" ]; then
        print_success "Виртуальное окружение найдено"
        
        # Проверка активации
        if [ -n "$VIRTUAL_ENV" ]; then
            print_success "Виртуальное окружение активно: $VIRTUAL_ENV"
        else
            print_warning "Виртуальное окружение не активно"
        fi
    else
        print_error "Виртуальное окружение не найдено"
    fi
}

# Проверка камеры
check_camera() {
    print_info "Проверка камеры..."
    
    # Проверка через vcgencmd
    if command -v vcgencmd >/dev/null 2>&1; then
        local camera_status=$(vcgencmd get_camera 2>/dev/null || echo "supported=0 detected=0")
        if echo "$camera_status" | grep -q "supported=1 detected=1"; then
            print_success "Камера обнаружена через vcgencmd"
        else
            print_warning "Камера не обнаружена через vcgencmd: $camera_status"
        fi
    fi
    
    # Проверка через libcamera
    if command -v libcamera-hello >/dev/null 2>&1; then
        if libcamera-hello --list-cameras 2>/dev/null | grep -q "Available cameras"; then
            print_success "Камера обнаружена через libcamera"
        else
            print_warning "Камера не обнаружена через libcamera"
        fi
    fi
}

# Проверка системных ресурсов
check_resources() {
    print_info "Проверка системных ресурсов..."
    
    # Температура CPU
    if command -v vcgencmd >/dev/null 2>&1; then
        local temp=$(vcgencmd measure_temp 2>/dev/null || echo "temp=N/A")
        print_info "Температура CPU: $temp"
    fi
    
    # Использование памяти
    local mem_info=$(free -h 2>/dev/null | grep "Mem:" || echo "N/A")
    print_info "Память: $mem_info"
    
    # Использование диска
    local disk_info=$(df -h . 2>/dev/null | tail -1 || echo "N/A")
    print_info "Диск: $disk_info"
    
    # Загрузка системы
    local load=$(uptime 2>/dev/null | awk -F'load average:' '{print $2}' || echo "N/A")
    print_info "Загрузка системы:$load"
}

# Основная функция
main() {
    print_header "Статус DC-Detector"
    
    check_processes
    echo ""
    check_systemd
    echo ""
    check_ports
    echo ""
    check_files
    echo ""
    check_venv
    echo ""
    check_camera
    echo ""
    check_resources
    
    print_header "Завершение проверки"
}

# Запуск
main "$@"
