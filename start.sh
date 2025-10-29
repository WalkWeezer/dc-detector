#!/bin/bash
# Запуск системы детекции огня DC-Detector
# Запускает camera-service и detection-service параллельно

echo "========================================"
echo "  DC-Detector - Запуск системы"
echo "========================================"
echo ""

# Получаем директорию скрипта
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Проверка наличия Python
if ! command -v python3 &> /dev/null; then
    echo "[ОШИБКА] Python3 не найден! Установите Python 3.8+"
    exit 1
fi

echo "[INFO] Python найден: $(python3 --version)"
echo ""

# Проверка наличия необходимых файлов
if [ ! -f "camera-service/camera_server.py" ]; then
    echo "[ОШИБКА] Файл camera-service/camera_server.py не найден!"
    exit 1
fi

if [ ! -f "detection-service/detection_server.py" ]; then
    echo "[ОШИБКА] Файл detection-service/detection_server.py не найден!"
    exit 1
fi

if [ ! -f "bestfire.pt" ]; then
    echo "[ПРЕДУПРЕЖДЕНИЕ] Файл bestfire.pt не найден в корне проекта!"
    echo "[ПРЕДУПРЕЖДЕНИЕ] Detection Service может не работать"
    echo ""
fi

# Функция для очистки при выходе
cleanup() {
    echo ""
    echo "[INFO] Остановка сервисов..."
    kill $CAMERA_PID 2>/dev/null
    kill $DETECTION_PID 2>/dev/null
    wait $CAMERA_PID 2>/dev/null
    wait $DETECTION_PID 2>/dev/null
    echo "[INFO] Сервисы остановлены"
    exit 0
}

# Перехватываем сигналы завершения
trap cleanup SIGINT SIGTERM

echo "[INFO] Запуск Camera Service (порт 8000)..."
cd "$SCRIPT_DIR/camera-service"
python3 camera_server.py &
CAMERA_PID=$!
cd "$SCRIPT_DIR"

# Даем время camera-service запуститься
sleep 3

echo "[INFO] Запуск Detection Service (порт 8001)..."
cd "$SCRIPT_DIR/detection-service"
python3 detection_server.py &
DETECTION_PID=$!
cd "$SCRIPT_DIR"

echo ""
echo "========================================"
echo "  Сервисы запущены!"
echo "========================================"
echo ""
echo "Camera Service:    http://localhost:8000"
echo "Detection Service: http://localhost:8001"
echo ""
echo "Для остановки нажмите Ctrl+C"
echo ""

# Ждем завершения процессов
wait $CAMERA_PID
wait $DETECTION_PID

