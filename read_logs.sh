#!/bin/bash

# 📄 DC-Detector Log Reader
# Скрипт для чтения логов установки
# Версия: 1.0

# Цвета
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}📄 $1${NC}"
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

# Поиск логов
find_logs() {
    print_header "Поиск логов установки"
    
    LOG_FILES=$(ls setup_log_*.log 2>/dev/null | sort -r)
    
    if [ -z "$LOG_FILES" ]; then
        print_error "Логи установки не найдены"
        echo "Ищите файлы с именем setup_log_*.log"
        exit 1
    fi
    
    print_info "Найдены следующие логи:"
    echo "$LOG_FILES" | nl
    echo ""
}

# Показать последний лог
show_latest_log() {
    LATEST_LOG=$(ls setup_log_*.log 2>/dev/null | sort -r | head -1)
    
    if [ -z "$LATEST_LOG" ]; then
        print_error "Логи не найдены"
        exit 1
    fi
    
    print_header "Последний лог установки: $LATEST_LOG"
    echo ""
    
    # Показать общую информацию
    print_info "Общая информация:"
    echo "Размер файла: $(du -h "$LATEST_LOG" | cut -f1)"
    echo "Дата создания: $(stat -c %y "$LATEST_LOG")"
    echo "Количество строк: $(wc -l < "$LATEST_LOG")"
    echo ""
    
    # Показать ошибки
    print_info "Ошибки в логе:"
    if grep -i "error\|failed\|не удалось\|ошибка" "$LATEST_LOG"; then
        echo ""
    else
        print_success "Ошибок не найдено"
        echo ""
    fi
    
    # Показать предупреждения
    print_info "Предупреждения в логе:"
    if grep -i "warning\|предупреждение\|warn" "$LATEST_LOG"; then
        echo ""
    else
        print_success "Предупреждений не найдено"
        echo ""
    fi
    
    # Показать успешные операции
    print_info "Успешные операции:"
    grep -i "success\|успешно\|установлен\|готов" "$LATEST_LOG" | tail -10
    echo ""
}

# Показать конкретный лог
show_specific_log() {
    if [ -z "$1" ]; then
        print_error "Укажите имя файла лога"
        echo "Использование: $0 show <имя_файла>"
        exit 1
    fi
    
    if [ ! -f "$1" ]; then
        print_error "Файл $1 не найден"
        exit 1
    fi
    
    print_header "Лог: $1"
    echo ""
    
    # Показать содержимое файла
    cat "$1"
}

# Показать только ошибки
show_errors() {
    LATEST_LOG=$(ls setup_log_*.log 2>/dev/null | sort -r | head -1)
    
    if [ -z "$LATEST_LOG" ]; then
        print_error "Логи не найдены"
        exit 1
    fi
    
    print_header "Ошибки в последнем логе: $LATEST_LOG"
    echo ""
    
    if grep -i "error\|failed\|не удалось\|ошибка" "$LATEST_LOG"; then
        echo ""
    else
        print_success "Ошибок не найдено"
    fi
}

# Показать только успешные операции
show_success() {
    LATEST_LOG=$(ls setup_log_*.log 2>/dev/null | sort -r | head -1)
    
    if [ -z "$LATEST_LOG" ]; then
        print_error "Логи не найдены"
        exit 1
    fi
    
    print_header "Успешные операции в последнем логе: $LATEST_LOG"
    echo ""
    
    grep -i "success\|успешно\|установлен\|готов" "$LATEST_LOG"
}

# Показать статистику
show_stats() {
    LATEST_LOG=$(ls setup_log_*.log 2>/dev/null | sort -r | head -1)
    
    if [ -z "$LATEST_LOG" ]; then
        print_error "Логи не найдены"
        exit 1
    fi
    
    print_header "Статистика лога: $LATEST_LOG"
    echo ""
    
    echo "Общая статистика:"
    echo "  Всего строк: $(wc -l < "$LATEST_LOG")"
    echo "  Размер файла: $(du -h "$LATEST_LOG" | cut -f1)"
    echo "  Дата создания: $(stat -c %y "$LATEST_LOG")"
    echo ""
    
    echo "Статистика по типам сообщений:"
    echo "  Ошибки: $(grep -c -i "error\|failed\|не удалось\|ошибка" "$LATEST_LOG")"
    echo "  Предупреждения: $(grep -c -i "warning\|предупреждение\|warn" "$LATEST_LOG")"
    echo "  Успешные операции: $(grep -c -i "success\|успешно\|установлен\|готов" "$LATEST_LOG")"
    echo "  Информационные сообщения: $(grep -c -i "info\|информация" "$LATEST_LOG")"
    echo ""
}

# Показать помощь
show_help() {
    print_header "Помощь по использованию"
    echo ""
    echo "Использование: $0 [команда] [параметры]"
    echo ""
    echo "Команды:"
    echo "  list                    - Показать список всех логов"
    echo "  latest                  - Показать последний лог"
    echo "  show <файл>            - Показать конкретный лог"
    echo "  errors                 - Показать только ошибки"
    echo "  success                - Показать только успешные операции"
    echo "  stats                  - Показать статистику лога"
    echo "  help                   - Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  $0 list"
    echo "  $0 latest"
    echo "  $0 show setup_log_20231201_143022.log"
    echo "  $0 errors"
    echo "  $0 success"
    echo "  $0 stats"
    echo ""
}

# Главная функция
main() {
    case "${1:-latest}" in
        "list")
            find_logs
            ;;
        "latest")
            show_latest_log
            ;;
        "show")
            show_specific_log "$2"
            ;;
        "errors")
            show_errors
            ;;
        "success")
            show_success
            ;;
        "stats")
            show_stats
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            print_error "Неизвестная команда: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Запуск главной функции
main "$@"
