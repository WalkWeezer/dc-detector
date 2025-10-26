#!/bin/bash

# 🔥 DC-Detector - Скрипт перезапуска системы детекции огня
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

# Остановка системы
stop_system() {
    print_info "Остановка DC-Detector..."
    
    # Остановка через systemd
    if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet fire-detection 2>/dev/null; then
        sudo systemctl stop fire-detection
        print_success "Systemd сервис остановлен"
    fi
    
    # Остановка процессов
    local pids=$(pgrep -f "python.*app_pi.py" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        print_info "Остановка процессов: $pids"
        for pid in $pids; do
            kill -TERM "$pid" 2>/dev/null || true
        done
        
        # Ждем завершения
        sleep 3
        
        # Принудительная остановка если нужно
        local remaining_pids=$(pgrep -f "python.*app_pi.py" 2>/dev/null || true)
        if [ -n "$remaining_pids" ]; then
            print_warning "Принудительная остановка процессов: $remaining_pids"
            for pid in $remaining_pids; do
                kill -KILL "$pid" 2>/dev/null || true
            done
        fi
    fi
    
    print_success "Система остановлена"
}

# Запуск системы
start_system() {
    print_info "Запуск DC-Detector..."
    
    # Проверка файлов
    if [ ! -f "app_pi.py" ] || [ ! -f "config_pi.py" ] || [ ! -f "bestfire.pt" ]; then
        print_error "Отсутствуют необходимые файлы"
        print_info "Убедитесь, что вы находитесь в директории проекта"
        exit 1
    fi
    
    # Проверка виртуального окружения
    if [ ! -d "fire_detection_env" ]; then
        print_error "Виртуальное окружение не найдено"
        print_info "Сначала запустите: ./install_dependencies.sh"
        exit 1
    fi
    
    # Запуск через systemd если доступен
    if command -v systemctl >/dev/null 2>&1 && systemctl is-enabled fire-detection >/dev/null 2>&1; then
        sudo systemctl start fire-detection
        print_success "Systemd сервис запущен"
        
        # Проверка статуса
        sleep 2
        if systemctl is-active --quiet fire-detection 2>/dev/null; then
            print_success "DC-Detector успешно запущен через systemd"
            print_info "Веб-интерфейс: http://localhost:5000"
            return 0
        else
            print_warning "Systemd сервис не запустился, пробуем прямой запуск"
        fi
    fi
    
    # Прямой запуск
    print_info "Прямой запуск приложения..."
    source fire_detection_env/bin/activate
    
    # Проверка Python модулей
    python3 -c "import cv2, ultralytics, flask, numpy" 2>/dev/null || {
        print_error "Не все Python модули установлены"
        print_info "Запустите: ./install_dependencies.sh"
        exit 1
    }
    
    print_success "Все проверки пройдены"
    print_info "Запуск приложения..."
    print_info "Веб-интерфейс будет доступен по адресу:"
    print_info "http://localhost:5000"
    print_info "http://$(hostname -I | awk '{print $1}'):5000"
    
    # Запуск в фоновом режиме
    nohup python3 app_pi.py > fire_detection.log 2>&1 &
    local pid=$!
    
    # Проверка запуска
    sleep 3
    if kill -0 "$pid" 2>/dev/null; then
        print_success "DC-Detector запущен (PID: $pid)"
        print_info "Логи: tail -f fire_detection.log"
    else
        print_error "Не удалось запустить DC-Detector"
        print_info "Проверьте логи: cat fire_detection.log"
        exit 1
    fi
}

# Основная функция
main() {
    print_header "Перезапуск DC-Detector"
    
    stop_system
    echo ""
    sleep 2
    start_system
    
    print_header "Перезапуск завершен"
}

# Обработка сигналов
trap 'echo -e "\n${YELLOW}Получен сигнал остановки...${NC}"; exit 0' INT TERM

# Запуск
main "$@"
