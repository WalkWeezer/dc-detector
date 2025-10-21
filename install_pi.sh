#!/bin/bash

# Скрипт установки Fire Detection System для Raspberry Pi
# Автор: DC-Detector Project
# Версия: 1.0

echo "🔥 Установка Fire Detection System для Raspberry Pi"
echo "=================================================="

# Проверяем, что мы на Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo; then
    echo "⚠️  Внимание: Этот скрипт предназначен для Raspberry Pi"
    read -p "Продолжить установку? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Обновляем систему
echo "📦 Обновление системы..."
sudo apt update && sudo apt upgrade -y

# Устанавливаем необходимые пакеты
echo "🔧 Установка системных зависимостей..."
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-opencv \
    libopencv-dev \
    libhdf5-dev \
    libhdf5-serial-dev \
    libatlas-base-dev \
    libjasper-dev \
    libqtgui4 \
    libqt4-test \
    libqt4-dev \
    libqt4-opengl-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libgtk-3-dev \
    libtbb2 \
    libtbb-dev \
    libdc1394-dev \
    v4l-utils \
    git \
    wget \
    curl

# Включаем камеру
echo "📷 Настройка камеры..."
sudo raspi-config nonint do_camera 0
echo "✅ Камера включена. Перезагрузка может потребоваться."

# Создаем виртуальное окружение
echo "🐍 Создание виртуального окружения..."
python3 -m venv fire_detection_env
source fire_detection_env/bin/activate

# Обновляем pip
echo "⬆️  Обновление pip..."
pip install --upgrade pip

# Устанавливаем PyTorch для ARM64 (оптимизированная версия)
echo "🧠 Установка PyTorch для Raspberry Pi..."
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Устанавливаем остальные зависимости
echo "📚 Установка Python зависимостей..."
pip install -r requirements.txt

# Создаем директорию для логов
echo "📁 Создание директорий..."
mkdir -p logs
mkdir -p models

# Создаем systemd сервис для автозапуска
echo "⚙️  Настройка автозапуска..."
sudo tee /etc/systemd/system/fire-detection.service > /dev/null <<EOF
[Unit]
Description=Fire Detection System
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/fire_detection_env/bin
ExecStart=$(pwd)/fire_detection_env/bin/python app_pi.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Перезагружаем systemd
sudo systemctl daemon-reload

# Создаем скрипт запуска
echo "🚀 Создание скрипта запуска..."
cat > start_fire_detection.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source fire_detection_env/bin/activate
python app_pi.py
EOF

chmod +x start_fire_detection.sh

# Создаем скрипт остановки
echo "🛑 Создание скрипта остановки..."
cat > stop_fire_detection.sh << 'EOF'
#!/bin/bash
sudo systemctl stop fire-detection
EOF

chmod +x stop_fire_detection.sh

# Настраиваем права доступа
echo "🔐 Настройка прав доступа..."
chmod +x *.sh
chown -R pi:pi .

# Получаем IP адрес
IP_ADDRESS=$(hostname -I | awk '{print $1}')

echo ""
echo "✅ Установка завершена!"
echo "========================"
echo ""
echo "🌐 Веб-интерфейс будет доступен по адресу:"
echo "   http://$IP_ADDRESS:5000"
echo "   http://localhost:5000"
echo ""
echo "🚀 Команды для управления:"
echo "   Запуск:     ./start_fire_detection.sh"
echo "   Остановка:  ./stop_fire_detection.sh"
echo "   Автозапуск: sudo systemctl enable fire-detection"
echo "   Статус:     sudo systemctl status fire-detection"
echo ""
echo "📋 Следующие шаги:"
echo "1. Убедитесь, что PiCamera подключена"
echo "2. Запустите систему: ./start_fire_detection.sh"
echo "3. Откройте браузер и перейдите по адресу выше"
echo ""
echo "⚠️  Важно: Перезагрузите Raspberry Pi для активации камеры!"
echo "   sudo reboot"
echo ""

# Спрашиваем о перезагрузке
read -p "Перезагрузить Raspberry Pi сейчас? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🔄 Перезагрузка..."
    sudo reboot
fi
