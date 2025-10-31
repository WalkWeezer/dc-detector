# 🔥 DC-Detector 2.0

Переосмысленная система детекции огня с четырьмя контейнерами:

- `frontend` — SPA на Vue (по наследию `yachi-ground-station`), отдаётся из nginx.
- `backend` — Node.js модульный монолит: REST API и учёт детекций, интеграция с БД.
- `detection` — Python/YOLO воркер: захват видеопотока, инференс, события в бэкенд.
- `db` — Postgres 16 (детекции).

Разработка — Windows/amd64, деплой — Raspberry Pi (Debian 64‑bit, arm64). Один набор Dockerfile собирается в multi‑arch образы.

## 📦 Структура

```
.
├── docker/
│   ├── backend.Dockerfile
│   ├── detection.Dockerfile
│   └── frontend.Dockerfile
├── docker-compose.yml            # dev/локальный запуск
├── docker-compose.prod.yml       # override для Raspberry Pi
├── services/
│   ├── backend/
│   │   ├── src/
│   │   └── package.json
│   └── detection/
│       ├── detection_server.py
│       ├── models/
│       └── requirements.txt
├── frontend/
├── infra/
│   └── db/migrations/            # SQL миграции Postgres
└── archive/                      # legacy код (к удалению после миграции)
```

## ⚙️ Требования

- Docker 24+, Docker Compose v2 (Windows: Desktop).
- Node.js 20 (локальная разработка фронта/бэка без контейнеров — опционально).
- Python 3.11 (локальный запуск detection — опционально).

## 🚀 Быстрый старт (dev, Windows/macOS/Linux)

1. Создайте `.env` в корне проекта (пример ниже) и при необходимости измените параметры подключения.

2. Поместите модель в `services/detection/models/bestfire.pt` (или используйте bind-монтирование по умолчанию).

3. Запустите стек:
   ```bash
   docker compose up --build
   ```

4. Доступы:
   - Frontend: <http://localhost>
   - Backend API: <http://localhost:8080>
   - Detection health: <http://localhost:8001/health>
   - Postgres: `localhost:5432` (логин/пароль `postgres/postgres`).

Пример `.env`:
```dotenv
PORT=8080
DATABASE_URL=postgres://postgres:postgres@db:5432/postgres
DETECTION_URL=http://detection:8001
JWT_SECRET=change-me

CAMERA_INDEX=0
CAMERA_SCAN_LIMIT=5
CAPTURE_RETRY_DELAY=1.0
MODEL_PATH=models/bestfire.pt
BACKEND_NOTIFY_URL=http://backend:8080/internal/detections
```

## 🐍 Detection service

- Автоматически сканирует локальные веб-камеры (индексы `0..CAMERA_SCAN_LIMIT`) и запускает поток с активного устройства.
- Эндпоинты:
  - `GET /cameras` — обновляет список доступных камер и выдаёт текущую.
  - `PATCH /cameras/<index>` — переключение на конкретную камеру.
  - `GET /video_feed` — MJPEG поток с наложенными детекциями.
  - `GET /api/detection` — текущее состояние детектора.
  - `POST /detect` — синхронный REST (изображение base64/URL).
- Отправляет события в `backend` (`/internal/detections`).

## 🟩 Backend (Node.js)

- REST:
  - `GET /api/detections`
  - `GET /api/detections/status`
  - `GET /api/detections/stream` — прокси MJPEG-потока с detection-сервиса
  - `POST /api/detections/run` — прокси к `detection`.
- Внутренние маршруты (не публикуются наружу):
  - `POST /internal/detections`
- Postgres: миграции SQL (таблица `detections`).

## 🧱 База данных

SQL миграции лежат в `infra/db/migrations`. При старте backend выполняет `runMigrations()` автоматически.

## 🏁 Raspberry Pi / прод режим

1. Соберите/push-ните multi‑arch образы (amd64+arm64) через Docker Buildx:
   ```bash
   docker buildx create --use
   docker buildx build \
     --platform linux/amd64,linux/arm64 \
     -t <registry>/dc-detector/backend:latest \
     -f docker/backend.Dockerfile . --push
   # то же для frontend и detection
   ```

2. На Raspberry Pi создайте `.env` с параметрами продакшена (секреты, RTSP URL).

3. Запустите:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

`docker-compose.prod.yml` добавляет `shm_size`, tmpfs и ограничения ресурсов для `detection`, а также `NODE_ENV=production`.

## 🔧 Полезные команды

- Логи: `docker compose logs -f backend detection`
- Выполнить миграции вручную: `docker compose exec backend node src/server.js`
- Просмотреть состояние БД: `docker compose exec db psql -U postgres`

## 🧑‍💻 Разработка с hot-reload

В репозитории есть `docker-compose.override.yml` (dev-override). Он автоматически подхватывается `docker compose` и включает горячую перезагрузку кода.

- Backend (Node 20): запускается как `node --watch src/server.js`, каталог `services/backend/src` примонтирован внутрь контейнера. Любые правки `.js` применяются сразу.
- Detection (Python/Flask): переменные `DEBUG=1` и `WATCHDOG_FORCE_POLLING=1` включены, файл `services/detection/detection_server.py` примонтирован. Правки применяются автоматически.
- Frontend (по умолчанию nginx): весь каталог `frontend/yachi-ground-station` примонтирован в `/usr/share/nginx/html` — правки HTML/CSS/JS видны мгновенно на `http://localhost`.

Опционально: полноценный Vite HMR

```bash
docker compose --profile dev up -d   # поднимет frontend-dev на http://localhost:5173
```

Базовый dev без Vite (nginx статика) — просто:

```bash
docker compose up -d
```

## 🧹 Очистка legacy

- После миграции удалить каталоги `camera-service/`, `detection-service/`, `archive/original-project/` и старые скрипты (`start.bat`, `start.ps1`, `start.sh`).
- Модели переместить из корня в `services/detection/models/`.

## 🤝 Вклад

1. Создайте ветку.
2. Выполните `docker compose build` и убедитесь, что сервисы проходят health-check.
3. Обновите документацию при изменениях API или конфигурации.

## 📄 Лицензия

MIT
