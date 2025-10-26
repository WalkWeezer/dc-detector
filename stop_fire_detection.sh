#!/bin/bash

# 🔥 DC-Detector - Скрипт остановки системы детекции огня
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

# Остановка через systemd
stop_systemd() {
    if systemctl is-active --quiet fire-detection 2>/dev/null; then
        print_info "Остановка systemd сервиса..."
        sudo systemctl stop fire-detection
        print_success "Systemd сервис остановлен"
    else
        print_info "Systemd сервис не запущен"
    fi
}

# Остановка через PID
stop_by_pid() {
    local pids=$(pgrep -f "python.*app_pi.py" 2>/dev/null || true)
    
    if [ -n "$pids" ]; then
        print_info "Найдены процессы DC-Detector: $pids"
        print_info "Остановка процессов..."
        
        for pid in $pids; do
            if kill -TERM "$pid" 2>/dev/null; then
                print_success "Процесс $pid остановлен"
            else
                print_warning "Не удалось остановить процесс $pid"
            fi
        done
        
        # Ждем завершения процессов
        sleep 2
        
        # Принудительная остановка если процессы еще работают
        local remaining_pids=$(pgrep -f "python.*app_pi.py" 2>/dev/null || true)
        if [ -n "$remaining_pids" ]; then
            print_warning "Принудительная остановка процессов: $remaining_pids"
            for pid in $remaining_pids; do
                kill -KILL "$pid" 2>/dev/null || true
            done
        fi
    else
        print_info "Процессы DC-Detector не найдены"
    fi
}

# Остановка по порту
stop_by_port() {
    local port=5000
    local pid=$(lsof -ti:$port 2>/dev/null || true)
    
    if [ -n "$pid" ]; then
        print_info "Найден процесс на порту $port: $pid"
        print_info "Остановка процесса..."
        
        if kill -TERM "$pid" 2>/dev/null; then
            print_success "Процесс на порту $port остановлен"
        else
            print_warning "Не удалось остановить процесс на порту $port"
        fi
    else
        print_info "Процессы на порту $port не найдены"
    fi
}

# Проверка статуса
check_status() {
    print_info "Проверка статуса..."
    
    local running_processes=$(pgrep -f "python.*app_pi.py" 2>/dev/null || true)
    local systemd_status=""
    
    if command -v systemctl >/dev/null 2>&1; then
        systemd_status=$(systemctl is-active fire-detection 2>/dev/null || echo "inactive")
    fi
    
    if [ -n "$running_processes" ]; then
        print_warning "DC-Detector все еще работает (PID: $running_processes)"
        return 1
    elif [ "$systemd_status" = "active" ]; then
        print_warning "Systemd сервис все еще активен"
        return 1
    else
        print_success "DC-Detector полностью остановлен"
        return 0
    fi
}

# Основная функция
main() {
    print_header "Остановка DC-Detector"
    
    stop_systemd
    stop_by_pid
    stop_by_port
    
    # Проверяем результат
    if check_status; then
        print_success "Система успешно остановлена"
    else
        print_error "Не удалось полностью остановить систему"
        print_info "Попробуйте запустить: sudo pkill -f 'python.*app_pi.py'"
        exit 1
    fi
}

# Запуск
main "$@"
