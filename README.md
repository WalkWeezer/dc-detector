# 🔥 DC-Detector 2.0

Система детекции огня с микросервисной архитектурой:

- `frontend` — легкий HTML/JS клиент (локальная камера, отрисовка bbox, сохранение клип‑GIFов)
- `backend` — Node.js REST API: прокси к detection-сервису и файловое хранилище детекций
- `detection` — Python/YOLO микросервис: захват видеопотока, инференс, трекинг объектов

## 📦 Структура

```
.
├── services/
│   ├── backend/                  # Node.js Backend API
│   └── detection/                # Python Detection Service
├── frontend/                     # HTML/JS Frontend
├── data/detections/              # JSON-файлы с результатами детекции
└── scripts/
    ├── start-prod.sh             # Запуск production
    └── stop-prod.sh              # Остановка production
```

## ⚙️ Требования

- **Detection Service**: Python 3.11+
- **Backend**: Node.js 20+
- **Frontend**: Node.js 20+ (для сборки)
- **Зависимости**: см. `services/detection/requirements.txt`

## 🚀 Быстрый старт

### Windows/ПК (Development)

```powershell
# Автоматический запуск
.\scripts\start-dev.bat

# Или вручную
cd services\detection && python detection_server.py
cd services\backend && node src\server.js
cd frontend && npm run dev
```

**Доступ:**
- Frontend: http://localhost:5173
- Backend: http://localhost:8080
- Detection: http://localhost:8001

### Raspberry Pi (Production)

```bash
# Автоматический запуск
chmod +x scripts/start-prod.sh
./scripts/start-prod.sh

# Остановка
./scripts/stop-prod.sh
```

**Доступ:**
- Frontend: http://localhost:5173 (или IP адрес Raspberry Pi:5173)
- Backend: http://localhost:8080
- Detection: http://localhost:8001

## 📋 Подготовка окружения

### 1. Создание .env файла

```bash
cp env.example .env
```

Важные переменные:
```dotenv
DETECTION_URL=http://localhost:8001
PORT=8080
```

### 2. Установка зависимостей Detection Service

```bash
cd services/detection
python3 -m venv ../../venv
source ../../venv/bin/activate
pip install -r requirements.txt
```

### 3. Модели YOLO

Поместите модели в `services/detection/models/`:
- `yolov8n.pt` (базовая модель)
- `bestfire.pt` (специализированная модель)

#### Оптимизация моделей для Raspberry Pi 4

Для улучшения производительности на Raspberry Pi 4 рекомендуется конвертировать модели в ONNX формат:

```bash
# Конвертация одной модели
python3 services/detection/scripts/optimize_models.py services/detection/models/yolov8n.pt --imgsz 640

# Автоматическая конвертация всех моделей
chmod +x scripts/optimize-models.sh
./scripts/optimize-models.sh
```

Поддерживаемые форматы:
- `.pt` - стандартный PyTorch формат
- `.onnx` - оптимизированный формат (рекомендуется для Raspberry Pi)
- `.ptl` - PyTorch Lite (если доступен)

## 🐍 Detection Service

### Оптимизация для Raspberry Pi 4

Проект оптимизирован для работы на Raspberry Pi 4 с следующими улучшениями:

1. **Оптимизация моделей**: Поддержка ONNX формата для ускорения инференса
2. **Очередь кадров**: Пропуск старых кадров для предотвращения накопления
3. **Ресайз перед инференсом**: Обработка кадров в уменьшенном разрешении (640x640)
4. **Буфер сырых кадров**: Сохранение последних 30 кадров для GIF без пропуска
5. **Настраиваемый FPS**: Контроль частоты обработки кадров
6. **Оптимизация памяти**: Копирование кадров только при необходимости
7. **Упрощенный трекинг**: Матчинг только по текущему bbox без предсказаний
8. **Отключение отрисовки**: Опция отключения отрисовки детекций на сервере
9. **Оптимизация логирования**: Возможность отключения логирования в production

#### Настройка производительности через UI

В интерфейсе доступна вкладка "Производительность" с настройками:
- FPS обработки (0.5 - 30)
- Порог уверенности (0.1 - 1.0)
- Качество JPEG для потока (10 - 100)
- Размер очереди кадров (1 - 10)
- Размер входного изображения (320, 640, 1280)
- Отключение отрисовки детекций

#### Переменные окружения для оптимизации

```bash
# FPS обработки
INFER_FPS=5.0

# Размер входного изображения для инференса (640 рекомендуется)
INPUT_SIZE=640

# Качество JPEG для потока и сохранения
JPEG_QUALITY_STREAM=60  # Для MJPEG потока (ниже = меньше нагрузка)
JPEG_QUALITY_SAVE=85     # Для сохранения детекций

# Размер очереди кадров
MAX_INFER_QUEUE_SIZE=2

# Размер буфера сырых кадров для GIF
RAW_FRAMES_BUFFER_SIZE=30

# Отключение отрисовки детекций на сервере
DRAW_DETECTIONS=false

# Отключение логирования в production
ENABLE_LOGGING=false
```

### Запуск

```bash
cd services/detection
source ../../venv/bin/activate
python detection_server.py
```

### Эндпоинты

- `GET /video_feed_raw` — сырой MJPEG поток
- `GET /video_feed` — MJPEG с детекциями
- `GET /api/trackers` — список трекеров
- `GET /api/detection` — статус детекции
- `GET /health` — health check
- `POST /models` — переключение модели

### Настройка камеры

**Raspberry Pi:**
```bash
# Для Pi Camera
export LOCAL_CAMERA_ENABLED=1
export CAMERA_BACKEND=PICAMERA2

# Для USB камеры
export LOCAL_CAMERA_ENABLED=1
export CAMERA_INDEX=0
export CAMERA_BACKEND=V4L2
```

**Переворот/поворот изображения:**
```bash
export FLIP_HORIZONTAL=true    # Горизонтальный переворот
export FLIP_VERTICAL=true      # Вертикальный переворот
export ROTATE_ANGLE=180        # Поворот на угол (0, 90, 180, 270)
```

## 🔧 Сервоприводы (Pan/Tilt)

### GPIO подключение (2 сервопривода)

**Подключение:**
- Pan серво: GPIO 18 (пин 12) - Signal, 5V - VCC, GND - GND
- Tilt серво: GPIO 19 (пин 35) - Signal, 5V - VCC, GND - GND

**Настройка:**
```bash
export SERVO_HARDWARE=gpio
export SERVO_PAN_PIN=18
export SERVO_TILT_PIN=19
export SERVO_FREQUENCY=50
```

**Установка зависимости:**
```bash
pip install RPi.GPIO
```

### PCA9685 подключение

**Настройка:**
```bash
export SERVO_HARDWARE=pca9685
export SERVO_PAN_CHANNEL=0
export SERVO_TILT_CHANNEL=1
export SERVO_PCA9685_ADDRESS=0x40
```

**Установка зависимости:**
```bash
pip install adafruit-circuitpython-servokit
```

**Включение I2C:**
```bash
sudo raspi-config
# Interface Options → I2C → Enable
```

## 🔄 Автозапуск (systemd)

Самый простой способ — использовать один systemd сервис, который запускает скрипт `start-prod.sh`:

```bash
# 1. Копируем service файл
sudo cp systemd/dc-detector.service /etc/systemd/system/

# 2. Обновляем путь в сервисе (замените на ваш путь к проекту)
sudo sed -i 's|/opt/dc-detector|/home/pi/dc-detector|g' /etc/systemd/system/dc-detector.service

# 3. Убедитесь, что скрипты исполняемые
chmod +x scripts/start-prod.sh scripts/stop-prod.sh

# 4. Включаем автозапуск
sudo systemctl daemon-reload
sudo systemctl enable dc-detector.service
sudo systemctl start dc-detector.service
```

**Управление:**
```bash
# Статус
sudo systemctl status dc-detector

# Запуск/остановка
sudo systemctl start dc-detector
sudo systemctl stop dc-detector

# Логи (важно для отладки!)
sudo journalctl -u dc-detector -f
sudo journalctl -u dc-detector -n 100  # Последние 100 строк
```

**Проверка после перезагрузки:**
```bash
# После перезагрузки Raspberry Pi проверьте:
sudo systemctl status dc-detector
curl http://localhost:8001/health  # Detection Service
curl http://localhost:8080/health # Backend
curl http://localhost:5173        # Frontend
```

**Если сервис не запускается:**
```bash
# 1. Проверьте логи для диагностики
sudo journalctl -u dc-detector -n 50 --no-pager

# 2. Проверьте, что скрипт работает вручную
./scripts/start-prod.sh

# 3. Проверьте права доступа
ls -la scripts/start-prod.sh
ls -la scripts/stop-prod.sh

# 4. Проверьте, что Node.js установлен
node --version
npm --version
```

## 🐛 Устранение проблем

### Backend не может подключиться к Detection Service

1. Проверьте, что Detection Service запущен:
```bash
curl http://localhost:8001/health
```

2. Проверьте `DETECTION_URL` в `.env`:
```bash
grep DETECTION_URL .env
# Должно быть: DETECTION_URL=http://localhost:8001
```

### Ошибка сохранения детекций

1. Проверьте права доступа:
```bash
sudo chown -R pi:pi data/detections/
chmod -R 755 data/detections/
```

2. Проверьте зависимости backend:
```bash
cd services/backend
npm list sharp gif-encoder-2 jpeg-js
```

### Сервоприводы не работают

1. Проверьте подключение проводов
2. Убедитесь, что установлена библиотека (`RPi.GPIO` или `adafruit-circuitpython-servokit`)
3. Проверьте логи: `journalctl -u dc-detection -f`
4. Для PCA9685 проверьте I2C: `i2cdetect -y 1`

### Камера не определяется

**Raspberry Pi:**
```bash
# Проверка Pi Camera
vcgencmd get_camera

# Включение камеры
sudo raspi-config
# Интерфейсы → Камера → Включить
```

**USB камера:**
```bash
lsusb
ls -l /dev/video*
```

## 📝 Полезные команды

**Detection Service:**
```bash
# Логи
tail -f .detection.log
# или
sudo journalctl -u dc-detection -f

# Статус
curl http://localhost:8001/api/detection
```

**Backend и Frontend:**
```bash
# Логи Backend
tail -f .backend.log

# Логи Frontend
tail -f .frontend.log

# Статус процессов
ps aux | grep -E "(node|vite)" | grep -v grep
```

**Проверка всех сервисов:**
```bash
curl http://localhost:8001/health && echo "✅ Detection"
curl http://localhost:8080/health && echo "✅ Backend"
curl http://localhost:5173 && echo "✅ Frontend"
```

## 📄 Лицензия

MIT
