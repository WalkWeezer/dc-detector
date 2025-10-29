#!/bin/bash
# Скрипт установки PyTorch на Raspberry Pi
# Использование: bash setup_raspberrypi.sh

set -e

echo "🔍 Определение архитектуры системы..."
ARCH=$(uname -m)
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)

echo "Архитектура: $ARCH"
echo "Версия Python: $PYTHON_VERSION"

# Обновление pip
echo "📦 Обновление pip..."
pip3 install --upgrade pip setuptools wheel

# Установка системных зависимостей
echo "📦 Установка системных зависимостей..."
sudo apt-get update
sudo apt-get install -y python3-dev libopenblas-dev libblas-dev libatlas-base-dev liblapack-dev

# Попытка установки PyTorch
echo "📦 Попытка установки PyTorch..."

if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    echo "Обнаружена 64-bit система (ARM64)"
    
    echo "Попытка 1: Установка через piwheels..."
    if pip3 install torch torchvision 2>/dev/null; then
        echo "✅ PyTorch установлен через piwheels"
    else
        echo "❌ Не удалось установить через piwheels"
        echo "Попытка 2: Установка через официальный индекс..."
        if pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cpu 2>/dev/null; then
            echo "✅ PyTorch установлен через официальный индекс"
        else
            echo "❌ Установка не удалась. Попробуйте установить вручную."
            exit 1
        fi
    fi
elif [ "$ARCH" = "armv7l" ] || [ "$ARCH" = "armhf" ]; then
    echo "Обнаружена 32-bit система (ARM32)"
    
    echo "Попытка 1: Установка через piwheels..."
    if pip3 install torch torchvision 2>/dev/null; then
        echo "✅ PyTorch установлен через piwheels"
    else
        echo "❌ Не удалось установить через piwheels"
        echo "Попытка 2: Установка конкретной версии..."
        if pip3 install torch==2.0.0 torchvision==0.15.0 --extra-index-url https://download.pytorch.org/whl/cpu 2>/dev/null; then
            echo "✅ PyTorch установлен"
        else
            echo "❌ Установка не удалась."
            echo "💡 Для ARM32 может потребоваться компиляция из исходников:"
            echo "   pip3 install torch torchvision --no-binary torch,torchvision"
            echo "   (Это займет 4-6 часов)"
            exit 1
        fi
    fi
else
    echo "❌ Неизвестная архитектура: $ARCH"
    exit 1
fi

# Установка ultralytics
echo "📦 Установка ultralytics..."
pip3 install ultralytics

# Установка остальных зависимостей
echo "📦 Установка остальных зависимостей..."
pip3 install flask opencv-python numpy requests Pillow Werkzeug urllib3

# Проверка установки
echo "🔍 Проверка установки..."
python3 -c "import torch; print(f'✅ PyTorch {torch.__version__} установлен')" || {
    echo "❌ Ошибка: PyTorch не импортируется"
    exit 1
}

python3 -c "import ultralytics; print('✅ Ultralytics установлен')" || {
    echo "❌ Ошибка: Ultralytics не импортируется"
    exit 1
}

echo ""
echo "✅ Установка завершена успешно!"
echo "🚀 Теперь вы можете запустить сервис:"
echo "   cd detection-service"
echo "   python3 detection_server.py"

