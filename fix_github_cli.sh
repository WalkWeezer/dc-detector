#!/bin/bash

# 🔧 GitHub CLI Fix Script
# Скрипт для исправления проблем с GitHub CLI репозиторием
# Версия: 1.0

# Цвета
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}🔧 $1${NC}"
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

# Удаление GitHub CLI репозитория
remove_github_cli_repo() {
    print_header "Удаление GitHub CLI репозитория"
    
    print_info "Проверка наличия GitHub CLI репозитория..."
    
    if [ -f "/etc/apt/sources.list.d/github-cli.list" ]; then
        print_info "Удаление файла репозитория..."
        sudo rm /etc/apt/sources.list.d/github-cli.list
        print_success "GitHub CLI репозиторий удален"
    else
        print_info "GitHub CLI репозиторий не найден"
    fi
    
    # Удаление ключа GPG
    print_info "Удаление GPG ключа GitHub CLI..."
    sudo rm -f /usr/share/keyrings/githubcli-archive-keyring.gpg
    print_success "GPG ключ удален"
}

# Очистка кэша apt
clean_apt_cache() {
    print_header "Очистка кэша apt"
    
    print_info "Очистка кэша пакетов..."
    sudo apt clean
    sudo apt autoclean
    
    print_info "Обновление списков пакетов..."
    sudo apt update
    
    print_success "Кэш очищен"
}

# Проверка системы
check_system() {
    print_header "Проверка системы"
    
    print_info "Информация о системе:"
    echo "  ОС: $(lsb_release -d | cut -f2)"
    echo "  Архитектура: $(uname -m)"
    echo "  Ядро: $(uname -r)"
    echo ""
    
    print_info "Проверка подключения к интернету..."
    if ping -c 1 8.8.8.8 >/dev/null 2>&1; then
        print_success "Интернет соединение работает"
    else
        print_warning "Проблемы с интернет соединением"
    fi
}

# Тест обновления
test_apt_update() {
    print_header "Тест обновления apt"
    
    print_info "Проверка обновления пакетов..."
    sudo apt update 2>&1 | tee test_update.log
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "Обновление apt работает корректно"
        rm -f test_update.log
    else
        print_warning "Обнаружены проблемы с apt update"
        echo ""
        print_info "Ошибки в обновлении:"
        grep -i "error\|failed" test_update.log || echo "Нет ошибок в логе"
        echo ""
        print_info "Полный лог сохранен в test_update.log"
    fi
}

# Установка необходимых пакетов
install_essential_packages() {
    print_header "Установка необходимых пакетов"
    
    print_info "Установка основных пакетов..."
    sudo apt install -y python3-pip python3-venv python3-dev python3-opencv libopencv-dev git wget curl build-essential cmake pkg-config
    
    if [ $? -eq 0 ]; then
        print_success "Основные пакеты установлены"
    else
        print_error "Ошибка установки основных пакетов"
        return 1
    fi
}

# Главная функция
main() {
    print_header "GitHub CLI Fix Script"
    print_info "Исправление проблем с GitHub CLI репозиторием"
    echo ""
    
    check_system
    remove_github_cli_repo
    clean_apt_cache
    test_apt_update
    install_essential_packages
    
    print_header "Исправление завершено"
    print_success "Проблемы с GitHub CLI репозиторием исправлены"
    echo ""
    print_info "Теперь можно запустить setup.sh:"
    echo "  ./setup.sh"
    echo ""
}

# Запуск главной функции
main "$@"
