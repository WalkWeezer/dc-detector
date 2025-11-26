# 🔥 DC-Detector 2.0

Система детекции огня с микросервисной архитектурой:

- `frontend` — легкий HTML/JS клиент (локальная камера, отрисовка bbox, сохранение клип‑GIFов)
- `backend` — Node.js REST API: прокси к detection-сервису и файловое хранилище детекций
- `detection` — Python/YOLO микросервис: захват видеопотока, инференс, трекинг объектов

**Важно:** Detection Service запускается **отдельно от Docker** для лучшей работы с камерой.

## 📦 Структура

```
.
├── docker/
│   ├── backend.Dockerfile
│   └── frontend.Dockerfile
├── docker-compose.yml            # базовый compose (backend + frontend)
├── docker-compose.dev.yml        # Windows dev (Vite hot-reload)
├── docker-compose.prod.yml       # Production (Raspberry Pi)
├── services/
│   ├── backend/
│   └── detection/
├── frontend/
├── data/detections/              # JSON-файлы с результатами детекции
└── scripts/
    ├── start-prod.sh             # Запуск production
    └── stop-prod.sh              # Остановка production
```

## ⚙️ Требования

- **Detection Service**: Python 3.11+, запускается отдельно от Docker
- **Backend/Frontend**: Docker 24+ или Node.js 20
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
- Frontend: http://localhost (или IP адрес Raspberry Pi)
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

## 🐍 Detection Service

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

## 🐳 Docker Compose

### Development

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### Production (Raspberry Pi)

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

**Важно:** `docker-compose.prod.yml` использует `network_mode: host` для backend, чтобы он мог обращаться к `localhost:8001` (Detection Service).

## 🔄 Автозапуск (systemd)

```bash
# Копируем service файлы
sudo cp systemd/dc-detection.service /etc/systemd/system/
sudo cp systemd/dc-detector.service /etc/systemd/system/

# Обновляем пути (замените на ваш путь)
sudo sed -i 's|/opt/dc-detector|/home/pi/dc-detector|g' /etc/systemd/system/*.service

# Включаем автозапуск
sudo systemctl daemon-reload
sudo systemctl enable dc-detection.service dc-detector.service
sudo systemctl start dc-detection.service dc-detector.service
```

**Управление:**
```bash
sudo systemctl start/stop/status dc-detection
sudo systemctl start/stop/status dc-detector
sudo journalctl -u dc-detection -f
sudo journalctl -u dc-detector -f
```

## 🐛 Устранение проблем

### Ошибка "mutually exclusive network_mode and networks"

**Решение:** Используйте `docker-compose.prod.yml`:
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

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

3. Для Raspberry Pi с `network_mode: host` используйте:
```bash
DETECTION_URL=http://localhost:8001
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

**Docker сервисы:**
```bash
# Логи
docker compose -f docker-compose.prod.yml logs -f

# Статус
docker compose -f docker-compose.prod.yml ps

# Перезапуск
docker compose -f docker-compose.prod.yml restart
```

**Проверка всех сервисов:**
```bash
curl http://localhost:8001/health && echo "✅ Detection"
curl http://localhost:8080/health && echo "✅ Backend"
curl http://localhost && echo "✅ Frontend"
```

## 📄 Лицензия

MIT
