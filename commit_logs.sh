#!/bin/bash

# 📝 DC-Detector Log Committer
# Скрипт для автоматического коммита логов установки
# Версия: 1.0

# Цвета
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}📝 $1${NC}"
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

# Проверка Git репозитория
check_git_repo() {
    if [ ! -d ".git" ]; then
        print_error "Это не Git репозиторий"
        exit 1
    fi
    print_success "Git репозиторий найден"
}

# Поиск новых логов
find_new_logs() {
    print_header "Поиск новых логов"
    
    # Найти все логи, которые не в Git
    NEW_LOGS=$(git ls-files --others --exclude-standard | grep "setup_log_.*\.log$")
    
    if [ -z "$NEW_LOGS" ]; then
        print_info "Новых логов не найдено"
        return 0
    fi
    
    print_info "Найдены новые логи:"
    echo "$NEW_LOGS"
    echo ""
    
    # Найти измененные логи
    MODIFIED_LOGS=$(git diff --name-only | grep "setup_log_.*\.log$")
    if [ ! -z "$MODIFIED_LOGS" ]; then
        print_info "Найдены измененные логи:"
        echo "$MODIFIED_LOGS"
        echo ""
    fi
    
    return 1
}

# Анализ логов
analyze_logs() {
    print_header "Анализ логов"
    
    for log_file in $NEW_LOGS $MODIFIED_LOGS; do
        if [ -f "$log_file" ]; then
            print_info "Анализ лога: $log_file"
            
            # Подсчет ошибок
            ERROR_COUNT=$(grep -c -i "error\|failed\|не удалось\|ошибка" "$log_file" 2>/dev/null || echo "0")
            
            # Подсчет предупреждений
            WARNING_COUNT=$(grep -c -i "warning\|предупреждение\|warn" "$log_file" 2>/dev/null || echo "0")
            
            # Подсчет успешных операций
            SUCCESS_COUNT=$(grep -c -i "success\|успешно\|установлен\|готов" "$log_file" 2>/dev/null || echo "0")
            
            echo "  Ошибки: $ERROR_COUNT"
            echo "  Предупреждения: $WARNING_COUNT"
            echo "  Успешные операции: $SUCCESS_COUNT"
            echo ""
            
            # Определить статус установки
            if [ "$ERROR_COUNT" -gt 0 ]; then
                STATUS="FAILED"
                print_error "Установка завершилась с ошибками"
            elif [ "$WARNING_COUNT" -gt 0 ]; then
                STATUS="WARNING"
                print_warning "Установка завершилась с предупреждениями"
            else
                STATUS="SUCCESS"
                print_success "Установка завершилась успешно"
            fi
            
            # Создать описание коммита
            COMMIT_MSG="Add setup log: $log_file (Status: $STATUS, Errors: $ERROR_COUNT, Warnings: $WARNING_COUNT)"
            echo "$COMMIT_MSG" >> commit_messages.txt
        fi
    done
}

# Коммит логов
commit_logs() {
    print_header "Коммит логов"
    
    # Добавить все логи в Git
    print_info "Добавление логов в Git..."
    git add setup_log_*.log 2>/dev/null || true
    
    # Проверить, есть ли изменения для коммита
    if git diff --cached --quiet; then
        print_info "Нет изменений для коммита"
        return 0
    fi
    
    # Создать коммит
    if [ -f "commit_messages.txt" ]; then
        COMMIT_MSG=$(cat commit_messages.txt | head -1)
        rm commit_messages.txt
    else
        COMMIT_MSG="Add setup installation logs"
    fi
    
    print_info "Создание коммита: $COMMIT_MSG"
    git commit -m "$COMMIT_MSG"
    
    if [ $? -eq 0 ]; then
        print_success "Логи успешно закоммичены"
    else
        print_error "Ошибка коммита логов"
        return 1
    fi
}

# Отправка в удаленный репозиторий
push_logs() {
    print_header "Отправка логов в удаленный репозиторий"
    
    print_info "Отправка в origin/main..."
    git push origin main
    
    if [ $? -eq 0 ]; then
        print_success "Логи успешно отправлены в удаленный репозиторий"
    else
        print_error "Ошибка отправки логов"
        return 1
    fi
}

# Создание отчета
create_report() {
    print_header "Создание отчета"
    
    REPORT_FILE="setup_report_$(date +%Y%m%d_%H%M%S).md"
    
    cat > "$REPORT_FILE" << EOF
# 📊 Setup Installation Report

**Дата создания:** $(date)
**Система:** $(uname -a)

## 📋 Обзор логов

EOF

    # Добавить информацию о каждом логе
    for log_file in setup_log_*.log; do
        if [ -f "$log_file" ]; then
            echo "### Лог: $log_file" >> "$REPORT_FILE"
            echo "" >> "$REPORT_FILE"
            echo "**Размер:** $(du -h "$log_file" | cut -f1)" >> "$REPORT_FILE"
            echo "**Дата:** $(stat -c %y "$log_file")" >> "$REPORT_FILE"
            echo "**Строк:** $(wc -l < "$log_file")" >> "$REPORT_FILE"
            echo "" >> "$REPORT_FILE"
            
            # Статистика
            ERROR_COUNT=$(grep -c -i "error\|failed\|не удалось\|ошибка" "$log_file" 2>/dev/null || echo "0")
            WARNING_COUNT=$(grep -c -i "warning\|предупреждение\|warn" "$log_file" 2>/dev/null || echo "0")
            SUCCESS_COUNT=$(grep -c -i "success\|успешно\|установлен\|готов" "$log_file" 2>/dev/null || echo "0")
            
            echo "**Статистика:**" >> "$REPORT_FILE"
            echo "- Ошибки: $ERROR_COUNT" >> "$REPORT_FILE"
            echo "- Предупреждения: $WARNING_COUNT" >> "$REPORT_FILE"
            echo "- Успешные операции: $SUCCESS_COUNT" >> "$REPORT_FILE"
            echo "" >> "$REPORT_FILE"
            
            # Статус
            if [ "$ERROR_COUNT" -gt 0 ]; then
                echo "**Статус:** ❌ FAILED" >> "$REPORT_FILE"
            elif [ "$WARNING_COUNT" -gt 0 ]; then
                echo "**Статус:** ⚠️ WARNING" >> "$REPORT_FILE"
            else
                echo "**Статус:** ✅ SUCCESS" >> "$REPORT_FILE"
            fi
            echo "" >> "$REPORT_FILE"
        fi
    done
    
    echo "## 🔍 Анализ ошибок" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    
    # Найти все ошибки
    for log_file in setup_log_*.log; do
        if [ -f "$log_file" ]; then
            ERRORS=$(grep -i "error\|failed\|не удалось\|ошибка" "$log_file" 2>/dev/null)
            if [ ! -z "$ERRORS" ]; then
                echo "### Ошибки в $log_file:" >> "$REPORT_FILE"
                echo '```' >> "$REPORT_FILE"
                echo "$ERRORS" >> "$REPORT_FILE"
                echo '```' >> "$REPORT_FILE"
                echo "" >> "$REPORT_FILE"
            fi
        fi
    done
    
    print_success "Отчет создан: $REPORT_FILE"
}

# Главная функция
main() {
    print_header "DC-Detector Log Committer"
    print_info "Автоматический коммит логов установки"
    echo ""
    
    check_git_repo
    
    if find_new_logs; then
        print_info "Нет новых логов для коммита"
        exit 0
    fi
    
    analyze_logs
    commit_logs
    
    if [ "$1" = "--push" ]; then
        push_logs
    fi
    
    create_report
    
    print_success "Готово!"
    echo ""
    print_info "Использование:"
    echo "  $0          - Коммит логов локально"
    echo "  $0 --push   - Коммит и отправить в удаленный репозиторий"
    echo ""
}

# Запуск главной функции
main "$@"
