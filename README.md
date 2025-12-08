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
# Backend порт (рекомендуется использовать BACKEND_PORT)
BACKEND_PORT=8080
# Или PORT=8080 для обратной совместимости

# Detection Service порт (рекомендуется использовать DETECTION_PORT)
DETECTION_PORT=8001
# Или PORT=8001 для обратной совместимости

# URL Detection Service
DETECTION_URL=http://localhost:8001
```

**Важно:** Используйте `BACKEND_PORT` и `DETECTION_PORT` вместо одного `PORT`, чтобы избежать конфликтов при запуске обоих сервисов из одного `.env` файла.

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

## 📡 MavLink GPS (UART на GPIO)

### Подключение к автопилоту через UART

#### Вариант 1: Аппаратный UART (рекомендуется)

**Физическое подключение (Raspberry Pi):**
- **TX (GPIO 14, пин 8)** → RX автопилота
- **RX (GPIO 15, пин 10)** → TX автопилота
- **GND (пин 6)** → GND автопилота

#### Вариант 2: Software UART (если аппаратный занят)

**Рекомендуемые GPIO пины для Software UART:**

| Назначение | GPIO | Физический пин | Примечание |
|------------|------|----------------|------------|
| **Вариант 1 (рекомендуется):** | | | |
| TX (передача) | GPIO 4 | Пин 7 | Часто свободен, не конфликтует с I2C |
| RX (прием) | GPIO 17 | Пин 11 | Часто свободен |
| **Вариант 2:** | | | |
| TX | GPIO 22 | Пин 15 | Часто свободен |
| RX | GPIO 23 | Пин 16 | Часто свободен |
| **Вариант 3:** | | | |
| TX | GPIO 24 | Пин 18 | Часто свободен |
| RX | GPIO 25 | Пин 22 | Часто свободен |

**Схема подключения (пример для GPIO 4/17):**
```
Raspberry Pi          Автопилот
───────────           ──────────
GPIO 4 (пин 7)  ────> RX автопилота
GPIO 17 (пин 11) <─── TX автопилота
GND (пин 6)     ────> GND автопилота
```

**Физическое подключение для Software UART:**
- **TX (выбранный GPIO, например GPIO 4, пин 7)** → RX автопилота
- **RX (выбранный GPIO, например GPIO 17, пин 11)** → TX автопилота
- **GND (любой GND, например пин 6)** → GND автопилота

**Настройка Software UART (простой способ через config.txt):**

Для Raspberry Pi 4/5 можно использовать дополнительные аппаратные UART на любых GPIO:
```bash
sudo nano /boot/config.txt
# Добавьте в конец файла:
# Software UART на GPIO 4 (TX) и GPIO 17 (RX)
dtoverlay=uart3,txd3_pin=4,rxd3_pin=17
# Или используйте GPIO 22/23:
# dtoverlay=uart4,txd4_pin=22,rxd4_pin=23
```

После перезагрузки появится `/dev/ttyAMA2` (для uart3) или `/dev/ttyAMA3` (для uart4).

**Альтернативный способ через pigpio (если config.txt не подходит):**

1. Установите pigpio и socat:
```bash
sudo apt-get update
sudo apt-get install pigpio socat
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
```

2. Создайте скрипт для software UART:
```bash
sudo nano /usr/local/bin/softuart-mavlink.sh
```

Содержимое скрипта:
```bash
#!/bin/bash
# Software UART на GPIO 4 (TX) и GPIO 17 (RX) для MavLink
# Использует pigpio для bit-bang UART
sudo pigpiod
# Создаем виртуальный последовательный порт
socat -d -d pty,raw,echo=0,link=/dev/ttySOFT0,wait-slave EXEC:"python3 -c \"
import pigpio
import time
pi = pigpio.pi()
# Настройка GPIO 4 как TX, GPIO 17 как RX
# Здесь нужна реализация bit-bang UART через pigpio
\""
```

**Примечание:** Для простоты рекомендуется использовать метод через `config.txt` с `dtoverlay=uart3` или `uart4`.

**Настройка Software UART через config.txt (альтернативный метод):**

Для Raspberry Pi 4 можно использовать дополнительные аппаратные UART:
```bash
sudo nano /boot/config.txt
# Добавьте для UART на GPIO 4/17:
dtoverlay=uart3
# Или для других пинов:
dtoverlay=uart4,txd4_pin=4,rxd4_pin=17
```

После этого появится `/dev/ttyAMA2` или `/dev/ttyAMA3`.

**Настройка UART на Raspberry Pi:**

1. Включите UART через `raspi-config`:
```bash
sudo raspi-config
# Interface Options → Serial Port → Enable
# (Отключите login shell через serial, если предложат)
```

2. Или вручную через `/boot/config.txt`:
```bash
sudo nano /boot/config.txt
# Добавьте или раскомментируйте:
enable_uart=1
```

3. Проверьте доступные UART порты:
```bash
ls -l /dev/ttyAMA* /dev/serial*
# Обычно: /dev/ttyAMA0 (основной UART) или /dev/serial0 (симлинк)
```

4. Настройте в `.env`:
```bash
# Для основного аппаратного UART на GPIO 14/15:
MAVLINK_PORT=/dev/ttyAMA0
# или используйте симлинк
MAVLINK_PORT=/dev/serial0

# Для Software UART (если настроен через pigpio/socat):
MAVLINK_PORT=/dev/ttySOFT0

# Для дополнительного аппаратного UART (если настроен в config.txt):
MAVLINK_PORT=/dev/ttyAMA2  # или /dev/ttyAMA3

# Скорость для MavLink (обычно 57600 или 115200)
MAVLINK_BAUDRATE=57600
```

**Примечание:** Если основной UART (GPIO 14/15) занят Bluetooth или другим устройством, используйте Software UART на других GPIO пинах.

5. Установите зависимости:
```bash
pip install pymavlink
```

**Проверка подключения:**
```bash
# Проверьте, что порт доступен
ls -l /dev/ttyAMA0

# Проверьте права доступа (может потребоваться добавить пользователя в группу dialout)
sudo usermod -a -G dialout $USER
# Перелогиньтесь после этого
```

**Альтернативные варианты подключения:**

- **USB последовательный порт:**
  ```bash
  MAVLINK_PORT=/dev/ttyUSB0
  ```

- **UDP (например, через QGroundControl):**
  ```bash
  MAVLINK_PORT=udp:127.0.0.1:14550
  ```

- **TCP:**
  ```bash
  MAVLINK_PORT=tcp:192.168.1.100:5760
  ```

**Примечание:** GPS координаты автоматически сохраняются в метаданных при сохранении GIF файлов.

## 🔄 Автозапуск (systemd)

Самый простой способ — использовать один systemd сервис, который запускает скрипт `start-prod.sh`. Теперь сервис можно настраивать через отдельный `.env`.

```bash
# 1. Копируем service файл
sudo cp systemd/dc-detector.service /etc/systemd/system/

# 2. (Рекомендуется) создаём /etc/dc-detector.env из примера и указываем путь к репозиторию
sudo cp systemd/dc-detector.env.example /etc/dc-detector.env
sudo nano /etc/dc-detector.env   # PROJECT_ROOT=/home/pi/dc-detector и т.д.

# 3. Убедитесь, что скрипты исполняемые
chmod +x scripts/start-prod.sh scripts/stop-prod.sh

# 4. Включаем автозапуск
sudo systemctl daemon-reload
sudo systemctl enable dc-detector.service
sudo systemctl start dc-detector.service
```

Что делает env-файл:
- `PROJECT_ROOT` — абсолютный путь до репозитория (если оставить пустым, по умолчанию `/opt/dc-detector`).
- `DETECTION_START_INITIAL_SLEEP`, `DETECTION_HEALTH_ATTEMPTS`, `DETECTION_HEALTH_DELAY` — управления ожиданием запуска сервиса детекции после перезагрузки (можно увеличить, если камера поднимается долго).

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
