# 🔥 DC-Detector 2.0

Система детекции огня с микросервисной архитектурой:

- `frontend` — легкий HTML/JS клиент (локальная камера, отрисовка bbox, сохранение клип‑GIFов), может работать через nginx или Vite dev‑сервер.
- `backend` — Node.js REST API: прокси к detection-сервису и файловое хранилище детекций.
- `detection` — Python/YOLO микросервис: захват видеопотока, инференс, трекинг объектов. **Запускается отдельно от Docker** для лучшей работы с камерой.

Разработка — Windows/amd64, деплой — Raspberry Pi (Debian 64‑bit, arm64).

## 📦 Структура

```
.
├── docker/
│   ├── backend.Dockerfile
│   └── frontend.Dockerfile
├── docker-compose.yml            # базовый compose (backend + frontend)
├── docker-compose.dev.yml        # Windows dev (Vite hot-reload)
├── docker-compose.prod.yml      # Production (Raspberry Pi)
├── services/
│   ├── backend/
│   │   ├── src/
│   │   └── package.json
│   └── detection/
│       ├── detection_server.py   # запускается отдельно от Docker
│       ├── models/
│       └── requirements.txt
├── frontend/
├── data/
│   └── detections/               # JSON-файлы с результатами детекции (по датам)
├── systemd/
│   ├── dc-detection.service      # systemd service для Detection Service
│   └── dc-detector.service       # systemd service для Backend/Frontend
```

## ⚙️ Требования

- **Detection Service**: Python 3.11+ (обязательно, запускается отдельно)
- **Backend/Frontend**: Docker 24+, Docker Compose v2 (Windows: Desktop) или Node.js 20 для локального запуска
- **Зависимости Detection Service**: 
  - `ultralytics` (YOLO)
  - `opencv-python` 
  - `numpy`
  - См. `services/detection/requirements.txt`

## 🚀 Быстрый старт

### Для разработки на Windows/ПК

**Автоматический запуск всех сервисов:**

```powershell
.\scripts\start-dev.ps1
```

Скрипт автоматически:
- Проверит зависимости (Python, Node.js)
- Установит недостающие пакеты
- Запустит Detection Service (порт 8001)
- Запустит Backend (порт 8080)
- Запустит Frontend через Vite (порт 5173)

**Доступные сервисы:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8080
- Detection Service: http://localhost:8001

**Остановка всех сервисов:**
```powershell
.\scripts\stop-dev.ps1
```

**Ручной запуск (если нужно):**

1. Detection Service:
   ```powershell
   cd services\detection
   python detection_server.py
   ```

2. Backend (в новом терминале):
   ```powershell
   cd services\backend
   node src\server.js
   ```

3. Frontend (в новом терминале):
   ```powershell
   cd frontend
   npm run dev
   ```

### Для продакшна на Raspberry Pi

**Автоматический запуск всех сервисов:**

```bash
chmod +x scripts/start-prod.sh
./scripts/start-prod.sh
```

Скрипт автоматически:
- Проверит зависимости (Python, Docker, Docker Compose)
- Создаст виртуальное окружение если нужно
- Установит недостающие пакеты
- Запустит Detection Service в фоне (порт 8001)
- Запустит Backend и Frontend через Docker (порты 8080 и 80)

**Доступные сервисы:**
- Frontend: http://localhost (или IP адрес Raspberry Pi)
- Backend API: http://localhost:8080
- Detection Service: http://localhost:8001

**Остановка всех сервисов:**
```bash
chmod +x scripts/stop-prod.sh
./scripts/stop-prod.sh
```

**Ручной запуск (если нужно):**

1. Detection Service:
   ```bash
   cd services/detection
   source ../../venv/bin/activate
   python detection_server.py
   ```

2. Backend и Frontend через Docker:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

## 🌐 Доступ по сети (Ethernet)

Для доступа к фронтенду с других устройств в локальной сети:

### Dev режим (Vite):
1. Убедитесь, что в `vite.config.js` установлено `host: '0.0.0.0'` (уже настроено)
2. Запустите dev-сервер:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml up
   ```
3. Найдите IP-адрес вашего компьютера:
   - Windows: `ipconfig` (смотрите IPv4 адрес Ethernet адаптера)
   - Linux/macOS: `ip addr` или `ifconfig`
4. Откройте в браузере на другом устройстве:
   - Frontend: `http://<ваш-IP>:5173` (например, `http://192.168.1.100:5173`)
   - Backend API: `http://<ваш-IP>:8080`

### Production режим (Nginx):
1. Убедитесь, что порты 80 и 443 открыты в firewall
2. Запустите production стек:
   ```bash
   docker compose up --build
   ```
3. Откройте в браузере на другом устройстве:
   - Frontend: `http://<ваш-IP>` или `https://<ваш-IP>`
   - Backend API: `http://<ваш-IP>:8080`

### Важно:
- **Firewall**: Убедитесь, что Windows Firewall или другой firewall разрешает входящие подключения на порты 5173 (dev) или 80/443 (production) и 8080 (backend)
- **HTTPS для getUserMedia**: Для работы веб-камеры в браузере может потребоваться HTTPS. В production режиме используется самоподписанный сертификат (будет предупреждение в браузере)
- **CORS**: Backend автоматически определяет origin и разрешает запросы с любого хоста в dev режиме

Пример `.env` (или см. `env.example`):
```dotenv
PORT=8080
DETECTION_URL=http://localhost:8001  # URL detection service (запускается отдельно)
DETECTIONS_DIR=data/detections
JWT_SECRET=change-me
```

**Важно:** `DETECTION_URL` должен указывать на адрес, где запущен detection service. Если он запущен на том же хосте - используйте `http://localhost:8001`. Если на другом хосте - укажите его IP адрес.

**Примечание:** Файл `.env` автоматически создается из `env.example` при первом запуске через `./scripts/start-prod.sh` или через Docker Compose (init сервис).

## 🐍 Detection Service

**Важно:** Detection service запускается **отдельно от Docker** для лучшей работы с камерой и доступа к устройствам.

### Запуск Detection Service

**Windows/Linux/macOS:**
```bash
cd services/detection
python detection_server.py
```

**С указанием порта:**
```bash
PORT=8080 python detection_server.py
```

**С указанием индекса камеры:**
```bash
CAMERA_INDEX=0 python detection_server.py
```

### Особенности

- Автоматически сканирует локальные веб-камеры (индексы `0..4`) и запускает поток с активного устройства
- Поддерживает Picamera2 (нативный API для Raspberry Pi) и веб-камеры через OpenCV
- Автоматически загружает доступные модели YOLO из `services/detection/models/`
- Поддерживает переключение моделей через API (`POST /models`)

### Эндпоинты

#### Видеопотоки
- `GET /video_feed_raw` — сырой MJPEG поток без детекций (максимальная скорость).
- `GET /video_feed` — MJPEG поток с наложенными детекциями (bbox и метки).

#### Трекеры
- `GET /api/trackers` — список активных трекеров с метаданными (trackId, bbox, confidence, label).
- `GET /api/trackers/<track_id>/crop` — кропнутый кадр для трекера (JPEG, для создания GIF).
- `GET /api/trackers/<track_id>/frames` — последовательность кропнутых кадров для трекера (JSON с base64 кадрами, для создания GIF).

#### Управление моделями
- `GET /models` — список доступных моделей и активная модель.
- `POST /models` — переключение модели (тело: `{ "name": "model_name.pt" }`).

#### Система
- `GET /health` — health check (статус сервиса, активная камера, модель)
- `GET /api/detection` — детальный статус детекции (модель, трекер, поток)

## 🟩 Backend (Node.js)

- REST:
  - `GET /api/detections`
  - `GET /api/detections/status`
  - `GET /api/detections/stream` — прокси MJPEG-потока с detection-сервиса
  - `POST /api/detections/run` — прокси к `detection`.
- `GET /api/detections/models`, `POST /api/detections/models` — управление моделью детекции.
- Сохранения пользователем:
  - `POST /api/detections/save` — сохранить текущую детекцию и короткий GIF (тело: `{ detection, frames:[dataUrl...], fps }`).
  - `GET /api/detections/saved?date=YYYY-MM-DD` — список сохранённых за день.
  - Статические файлы по `/files/...` (от корня `data/`), например: `/files/detections/saved/2025-11-03/<id>.gif`.
- Внутренние маршруты (не публикуются наружу):
  - `POST /internal/detections`
- Хранит результаты в JSON-файлах (`data/detections/YYYY-MM-DD.json`).

## 🗃️ Хранилище детекций

- Backend автоматически создаёт каталог `data/detections` и ведёт файлы по датам (`YYYY-MM-DD.json`).
- Каждый объект содержит уникальный `id`, `trackId`, метки `firstSeen/lastSeen`, bbox и актуальную уверенность.
- Детекции с одинаковым `trackId` обновляются (не дублируются).

### Сохранённые пользователем (JSON + GIF)
- Путь: `data/detections/saved/YYYY-MM-DD/<id>.{json,gif}`
- JSON содержит метаданные детекции и относительные пути до GIF/JSON, GIF — клип из последних кадров (обычно 2–3 сек, ширина 320px).
- Доступ к файлам: `/files/detections/saved/YYYY-MM-DD/<id>.gif`.

## 🏁 Raspberry Pi / прод режим

> 📖 **Подробная инструкция по запуску detection service:** см. [RASPBERRY_PI_SETUP.md](RASPBERRY_PI_SETUP.md)

### Подготовка и инициализация

1. Склонируйте репозиторий на Raspberry Pi:
   ```bash
   git clone <repository-url>
   cd DC-Detector
   ```

2. Запустите скрипт инициализации для создания необходимых файлов и директорий:
   ```bash
   # Инициализация выполняется автоматически при запуске
   ./scripts/start-prod.sh
   ```
   Скрипт автоматически создаст `.env` из `env.example` (если его нет) и необходимые директории.

3. **Установите зависимости для Detection Service:**
   ```bash
   cd services/detection
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Запустите Detection Service:**
   ```bash
   cd services/detection
   source venv/bin/activate  # если еще не активировано
   python3 detection_server.py
   ```
   
   Или используйте готовый скрипт:
   ```bash
   cd services/detection && source ../../venv/bin/activate && python detection_server.py
   ```

5. **Запустите Backend и Frontend (в Docker):**
   ```bash
   # Убедитесь, что в .env указан правильный DETECTION_URL
   # DETECTION_URL=http://localhost:8001
   
   docker compose -f docker-compose.prod.yml up -d --build
   ```

### Автозапуск при загрузке системы

Для автоматического запуска всех сервисов при загрузке Raspberry Pi:

1. Установите systemd services:
   ```bash
   sudo ./scripts/install-systemd.sh
   ```

2. (Опционально) Укажите путь к проекту, если он не в стандартной директории:
   ```bash
   export DC_DETECTOR_PATH=/path/to/DC-Detector
   sudo -E ./scripts/install-systemd.sh
   ```

3. Управление сервисами:
   ```bash
   # Detection Service (отдельный сервис)
   sudo systemctl start dc-detection
   sudo systemctl stop dc-detection
   sudo systemctl status dc-detection
   sudo journalctl -u dc-detection -f
   
   # Backend и Frontend (Docker Compose)
   sudo systemctl start dc-detector
   sudo systemctl stop dc-detector
   sudo systemctl status dc-detector
   sudo journalctl -u dc-detector -f
   ```

### Видеопоток

В режиме Raspberry Pi фронтенд может показывать два варианта:
- Главная страница `/` — локальная камера клиента (удобно для разработки)
- Страница `/pi.html` — поток с камеры Raspberry Pi (серверный MJPEG)

Потоки на уровне API:
- `GET /api/detections/stream` — MJPEG c серверной разметкой (bbox рисует detection)
- `GET /api/detections/stream-raw` — «чистый» MJPEG без разметки (bbox рисует фронтенд)

Доступ к интерфейсу:
- По локальной сети: `http://<IP-raspberry-pi>/` или `https://<IP-raspberry-pi>/`
- На самом Raspberry Pi: `http://localhost/` или `https://localhost/`

### Проверка работоспособности после деплоя

После деплоя запустите автотесты для проверки всех компонентов:

```bash
# Проверка доступности сервисов
curl http://localhost:8001/health
curl http://localhost:8080/health
curl http://localhost
```

Скрипт проверит:
- Все эндпоинты backend и detection сервисов
- Доступность фронтенда
- Работоспособность Pi Camera
- Видеопоток

Параметры тестов можно настроить через переменные окружения:
```bash
BACKEND_URL=http://localhost:8080 \
DETECTION_URL=http://localhost:8001 \
FRONTEND_URL=http://localhost \
# Проверка доступности сервисов
curl http://localhost:8001/health
curl http://localhost:8080/health
curl http://localhost
```

`docker-compose.prod.yml` включает сборку фронта. Detection Service запускается отдельно и не требует Docker.

### Оптимизация FPS на Raspberry Pi

1. Настройте драйвер/формат камеры (на хосте):
   ```bash
   sudo modprobe bcm2835-v4l2
   v4l2-ctl -d /dev/video0 --set-fmt-video=width=640,height=480,pixelformat=MJPG
   v4l2-ctl -d /dev/video0 --set-parm=15
   ```

2. Рекомендуемые переменные окружения для Detection Service:
   ```bash
   export CAMERA_INDEX=0
   export CONFIDENCE_THRESHOLD=0.5
   export INFER_FPS=5  # FPS инференса YOLO
   export PORT=8001
   ```

3. Запустите с оптимизированными параметрами:
   ```bash
   CAMERA_INDEX=0 INFER_FPS=5 python3 detection_server.py
   ```

## 🔧 Полезные команды

**Detection Service:**
- Запуск: `cd services/detection && python detection_server.py`
- Проверка статуса: `curl http://localhost:8001/api/detection`
- Логи: смотрите вывод в терминале или systemd журнал

**Backend/Frontend (Docker):**
- Логи: `docker compose logs -f backend frontend`
- Просмотреть актуальные файлы детекций: `ls data/detections`
- Очистить данные детекций: удалить соответствующий `data/detections/YYYY-MM-DD.json`

## 🧑‍💻 Разработка с hot-reload

Для разработки используйте `docker-compose.dev.yml` (Vite HMR) поверх базового файла:

- **Detection Service**: запускается отдельно, правки в `detection_server.py` применяются после перезапуска
- **Backend (Node 20)**: запускается как `node --watch src/server.js`, каталог `services/backend/src` примонтирован внутрь контейнера. Любые правки `.js` применяются сразу.
- **Frontend**: каталог `frontend/` примонтирован в `/usr/share/nginx/html` — правки HTML/CSS/JS видны мгновенно на `http://localhost`.

Опционально: полноценный Vite HMR

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d   # frontend-dev на http://localhost:5173
```

Фронтенд особенности
- Кнопка «Сохранить» в списке детекций отправляет последние буферизованные кадры на `POST /api/detections/save`.
- Вкладка «Сохранённые» показывает миниатюры GIF и позволяет быстро проверять клипы. Обновление — кнопка «Обновить», фильтр по дате.

Базовый dev без Vite (nginx статика) — просто:

```bash
docker compose up -d
```

## 📄 Лицензия

MIT
