#!/bin/bash

# 🔥 DC-Detector - Быстрое создание виртуального окружения
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

# Проверка Python
check_python() {
    print_info "Проверка Python..."
    
    if command -v python3 >/dev/null 2>&1; then
        local python_version=$(python3 --version 2>&1)
        print_success "Python найден: $python_version"
        
        # Проверка версии
        local version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if [ "$(echo "$version >= 3.8" | bc -l 2>/dev/null || echo "1")" = "1" ]; then
            print_success "Версия Python подходящая: $version"
        else
            print_warning "Рекомендуется Python 3.8+, текущая версия: $version"
        fi
    else
        print_error "Python3 не найден"
        print_info "Установите Python3: sudo apt install python3 python3-pip python3-venv"
        exit 1
    fi
}

# Проверка venv модуля
check_venv_module() {
    print_info "Проверка модуля venv..."
    
    if python3 -m venv --help >/dev/null 2>&1; then
        print_success "Модуль venv доступен"
    else
        print_error "Модуль venv не найден"
        print_info "Установите python3-venv: sudo apt install python3-venv"
        exit 1
    fi
}

# Создание виртуального окружения
create_venv() {
    print_info "Создание виртуального окружения..."
    
    if [ -d "fire_detection_env" ]; then
        print_warning "Виртуальное окружение уже существует"
        read -p "Удалить существующее окружение? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Удаление существующего окружения..."
            rm -rf fire_detection_env
        else
            print_info "Используем существующее окружение"
            return 0
        fi
    fi
    
    print_info "Создание нового виртуального окружения..."
    python3 -m venv fire_detection_env
    
    if [ -d "fire_detection_env" ]; then
        print_success "Виртуальное окружение создано"
    else
        print_error "Не удалось создать виртуальное окружение"
        exit 1
    fi
}

# Активация и установка зависимостей
setup_dependencies() {
    print_info "Активация виртуального окружения..."
    source fire_detection_env/bin/activate
    
    print_info "Обновление pip..."
    pip install --upgrade pip
    
    if [ -f "requirements.txt" ]; then
        print_info "Установка зависимостей из requirements.txt..."
        pip install -r requirements.txt
        print_success "Зависимости установлены"
    else
        print_warning "Файл requirements.txt не найден"
        print_info "Установка основных зависимостей..."
        pip install opencv-python ultralytics flask numpy pillow
        print_success "Основные зависимости установлены"
    fi
}

# Проверка установки
verify_installation() {
    print_info "Проверка установки..."
    
    source fire_detection_env/bin/activate
    
    local modules=("cv2" "ultralytics" "flask" "numpy" "PIL")
    local missing_modules=()
    
    for module in "${modules[@]}"; do
        if python3 -c "import $module" 2>/dev/null; then
            print_success "Модуль $module установлен"
        else
            print_error "Модуль $module не найден"
            missing_modules+=("$module")
        fi
    done
    
    if [ ${#missing_modules[@]} -ne 0 ]; then
        print_error "Отсутствуют модули: ${missing_modules[*]}"
        print_info "Попробуйте переустановить: pip install ${missing_modules[*]}"
        return 1
    fi
    
    print_success "Все модули установлены корректно"
}

# Создание скрипта активации
create_activation_script() {
    print_info "Создание скрипта активации..."
    
    cat > activate_env.sh << 'EOF'
#!/bin/bash
# Скрипт активации виртуального окружения DC-Detector

if [ -d "fire_detection_env" ]; then
    source fire_detection_env/bin/activate
    echo "✅ Виртуальное окружение DC-Detector активировано"
    echo "Для деактивации выполните: deactivate"
else
    echo "❌ Виртуальное окружение не найдено"
    echo "Запустите: ./create_venv.sh"
    exit 1
fi
EOF
    
    chmod +x activate_env.sh
    print_success "Скрипт активации создан: activate_env.sh"
}

# Основная функция
main() {
    print_header "Создание виртуального окружения DC-Detector"
    
    check_python
    check_venv_module
    create_venv
    setup_dependencies
    verify_installation
    create_activation_script
    
    print_header "Готово!"
    print_success "Виртуальное окружение создано и настроено"
    print_info "Для активации используйте:"
    echo "  source fire_detection_env/bin/activate"
    echo "  или"
    echo "  ./activate_env.sh"
    echo ""
    print_info "Для запуска приложения:"
    echo "  ./start_fire_detection.sh"
}

# Запуск
main "$@"
