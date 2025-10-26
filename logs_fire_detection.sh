#!/bin/bash

# 🔥 DC-Detector - Скрипт просмотра логов системы детекции огня
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

# Параметры по умолчанию
LINES=50
FOLLOW=false
SYSTEMD=false
FILE_LOG=false

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -n|--lines)
            LINES="$2"
            shift 2
            ;;
        -s|--systemd)
            SYSTEMD=true
            shift
            ;;
        -h|--help)
            echo "Использование: $0 [опции]"
            echo ""
            echo "Опции:"
            echo "  -f, --follow     Следить за логами в реальном времени"
            echo "  -n, --lines N    Показать последние N строк (по умолчанию: 50)"
            echo "  -s, --systemd    Показать логи systemd вместо файловых"
            echo "  -h, --help       Показать эту справку"
            echo ""
            echo "Примеры:"
            echo "  $0                    # Последние 50 строк"
            echo "  $0 -n 100             # Последние 100 строк"
            echo "  $0 -f                 # Следить за логами"
            echo "  $0 -s                 # Логи systemd"
            echo "  $0 -s -f              # Следить за логами systemd"
            exit 0
            ;;
        *)
            print_error "Неизвестная опция: $1"
            echo "Используйте $0 --help для справки"
            exit 1
            ;;
    esac
done

# Проверка доступности systemd
check_systemd() {
    if command -v systemctl >/dev/null 2>&1; then
        if systemctl is-active fire-detection >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Показать логи systemd
show_systemd_logs() {
    print_header "Логи DC-Detector (systemd)"
    
    if ! check_systemd; then
        print_warning "Systemd сервис не активен"
        print_info "Попробуйте использовать файловые логи: $0"
        return 1
    fi
    
    print_info "Показ логов systemd сервиса fire-detection"
    echo ""
    
    if [ "$FOLLOW" = true ]; then
        print_info "Слежение за логами (Ctrl+C для выхода)..."
        journalctl -u fire-detection -f
    else
        journalctl -u fire-detection --no-pager -n "$LINES"
    fi
}

# Показать файловые логи
show_file_logs() {
    print_header "Логи DC-Detector (файлы)"
    
    local log_files=()
    
    # Поиск файлов логов
    if [ -f "fire_detection.log" ]; then
        log_files+=("fire_detection.log")
    fi
    
    if [ -f "app.log" ]; then
        log_files+=("app.log")
    fi
    
    if [ -f "error.log" ]; then
        log_files+=("error.log")
    fi
    
    # Поиск логов в директории logs
    if [ -d "logs" ]; then
        while IFS= read -r -d '' file; do
            log_files+=("$file")
        done < <(find logs -name "*.log" -print0 2>/dev/null)
    fi
    
    if [ ${#log_files[@]} -eq 0 ]; then
        print_warning "Файлы логов не найдены"
        print_info "Возможные причины:"
        echo "1. Приложение еще не запускалось"
        echo "2. Логи записываются в другое место"
        echo "3. Используйте systemd логи: $0 -s"
        return 1
    fi
    
    print_info "Найденные файлы логов: ${log_files[*]}"
    echo ""
    
    # Показать логи из всех файлов
    for log_file in "${log_files[@]}"; do
        if [ -f "$log_file" ]; then
            print_info "=== $log_file ==="
            
            if [ "$FOLLOW" = true ]; then
                print_info "Слежение за $log_file (Ctrl+C для выхода)..."
                tail -f "$log_file"
            else
                tail -n "$LINES" "$log_file"
            fi
            
            echo ""
        fi
    done
}

# Показать системные логи
show_system_logs() {
    print_header "Системные логи"
    
    print_info "Последние записи в /var/log/syslog связанные с DC-Detector:"
    echo ""
    
    if [ -r "/var/log/syslog" ]; then
        grep -i "fire-detection\|dc-detector\|app_pi" /var/log/syslog 2>/dev/null | tail -n "$LINES" || {
            print_warning "Нет записей в системных логах"
        }
    else
        print_warning "Нет доступа к /var/log/syslog"
        print_info "Запустите с sudo для доступа к системным логам"
    fi
}

# Показать информацию о процессах
show_process_info() {
    print_header "Информация о процессах"
    
    local pids=$(pgrep -f "python.*app_pi.py" 2>/dev/null || true)
    
    if [ -n "$pids" ]; then
        print_success "DC-Detector запущен (PID: $pids)"
        
        for pid in $pids; do
            print_info "Процесс $pid:"
            ps -p "$pid" -o pid,ppid,cmd,etime,pcpu,pmem 2>/dev/null || true
            echo ""
        done
    else
        print_warning "DC-Detector не запущен"
    fi
}

# Основная функция
main() {
    if [ "$SYSTEMD" = true ]; then
        show_systemd_logs
    else
        show_file_logs
    fi
    
    echo ""
    show_process_info
    echo ""
    show_system_logs
}

# Запуск
main "$@"
