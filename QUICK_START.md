# 🚀 Быстрый старт

**Важно:** Detection Service запускается **отдельно от Docker** для лучшей работы с камерой.

## 🖥️ Для разработки на Windows/ПК

### Автоматический запуск (рекомендуется)

```powershell
.\scripts\start-dev.ps1
```

Скрипт автоматически проверит и установит все зависимости, затем запустит все сервисы:
- Detection Service на порту 8001
- Backend на порту 8080
- Frontend (Vite) на порту 5173

**Остановка:**
```powershell
.\scripts\stop-dev.ps1
```

### Ручной запуск

1. **Detection Service:**
   ```powershell
   cd services\detection
   python detection_server.py
   ```

2. **Backend** (в новом терминале):
   ```powershell
   cd services\backend
   node src\server.js
   ```

3. **Frontend** (в новом терминале):
   ```powershell
   cd frontend
   npm run dev
   ```

Или через Docker:
```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

## 🍓 Для продакшна на Raspberry Pi

### Автоматический запуск (рекомендуется)

```bash
chmod +x scripts/start-prod.sh
./scripts/start-prod.sh
```

Скрипт автоматически:
- Проверит зависимости
- Создаст виртуальное окружение
- Установит недостающие пакеты
- Запустит Detection Service в фоне
- Запустит Backend и Frontend через Docker

**Остановка:**
```bash
chmod +x scripts/stop-prod.sh
./scripts/stop-prod.sh
```

### Ручной запуск

1. **Detection Service:**
   ```bash
   cd services/detection && source ../../venv/bin/activate && python detection_server.py
   ```

2. **Backend и Frontend через Docker:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

## 📋 Подготовка окружения

1. Установите зависимости для Detection Service:
   ```bash
   cd services/detection
   pip install -r requirements.txt
   ```

2. Поместите модель YOLO в `services/detection/models/`:
   - `yolov8n.pt` (базовая модель)
   - `bestfire.pt` (специализированная модель)

3. (Опционально) Запустите скрипт инициализации:
   ```bash
   # Инициализация выполняется автоматически при запуске
   ./scripts/start-prod.sh
   ```

## 🌐 Доступ к сервисам

**Разработка (Windows/ПК):**
- Frontend: http://localhost:5173
- Backend: http://localhost:8080
- Detection: http://localhost:8001

**Продакшн (Raspberry Pi):**
- Frontend: http://localhost (или IP адрес Raspberry Pi)
- Backend: http://localhost:8080
- Detection: http://localhost:8001

## 📝 Дополнительная информация

### Шаг 1: Установка зависимостей Detection Service

1. Установите системные пакеты:
   ```bash
   sudo apt update
   sudo apt install -y python3-picamera2 python3-pip python3-venv python3-full
   ```

2. Создайте виртуальное окружение и установите зависимости:
   ```bash
   cd services/detection
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

### Шаг 2: Запуск Detection Service

**Вариант A: Через скрипт (рекомендуется)**
```bash
./scripts/run-detection-direct.sh
```

**Вариант B: Вручную**
```bash
cd services/detection
source venv/bin/activate
python3 detection_server.py
```

Сервис будет доступен на `http://localhost:8001`
- Видеопоток: `http://localhost:8001/video_feed_raw`
- Health check: `http://localhost:8001/health`
- Статус детекции: `http://localhost:8001/api/detection`

### Шаг 3: Запуск Backend и Frontend (Docker)

1. Убедитесь, что в `.env` указан правильный `DETECTION_URL`:
   ```dotenv
   DETECTION_URL=http://localhost:8001
   ```

2. Запустите Backend и Frontend:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

### Автозапуск при загрузке системы

Для автоматического запуска всех сервисов при загрузке Raspberry Pi:

```bash
sudo cp systemd/dc-detection.service /etc/systemd/system/
sudo cp systemd/dc-detector.service /etc/systemd/system/
sudo sed -i 's|/opt/dc-detector|/home/pi/dc-detector|g' /etc/systemd/system/*.service
sudo systemctl daemon-reload
sudo systemctl enable dc-detection.service dc-detector.service
```

Управление:
- **Detection Service:**
  - `sudo systemctl start dc-detection` - запуск
  - `sudo systemctl stop dc-detection` - остановка
  - `sudo systemctl status dc-detection` - статус
  - `sudo journalctl -u dc-detection -f` - логи

- **Backend и Frontend (Docker):**
  - `sudo systemctl start dc-detector` - запуск
  - `sudo systemctl stop dc-detector` - остановка
  - `sudo systemctl status dc-detector` - статус
  - `sudo journalctl -u dc-detector -f` - логи

### Видеопоток

- Главная страница `/` или `/devtool.html` — поток с веб‑камеры клиента (как в Windows)
- Для режима «поток с фронтенда» на Raspberry Pi установите `LOCAL_CAMERA_ENABLED=0` в `.env`
- Откройте: `http://<IP-raspberry-pi>/devtool.html?async=true` — асинхронный поток с максимальным FPS
- Доступ по локальной сети: `http://<IP-raspberry-pi>/` или `https://<IP-raspberry-pi>/`
- Фронтенд обслуживается nginx на 80/443 (самоподписанный сертификат генерируется в образе).
- Для доступа к камере на IP используйте HTTPS: https://<IP>/ и примите сертификат. На `localhost` HTTPS не обязателен.

#### Оптимизация FPS на Raspberry Pi

1. Настройте камеру на хосте (V4L2):
   ```bash
   sudo modprobe bcm2835-v4l2
   v4l2-ctl -d /dev/video0 --set-fmt-video=width=640,height=480,pixelformat=MJPG
   v4l2-ctl -d /dev/video0 --set-parm=15
   ```

2. Рекомендуемые переменные в `.env`:
   ```dotenv
  # Для потока с фронтенда (камера клиента, как на Windows):
  LOCAL_CAMERA_ENABLED=0

  # Если хотите использовать Pi Camera напрямую (альтернативный режим):
  # VIDEO_DEVICE=/dev/video0
  # LOCAL_CAMERA_ENABLED=1
  # CAMERA_BACKEND=V4L2
  # CAMERA_INDEX=0
  # CAMERA_SCAN_LIMIT=1
  # CAPTURE_RETRY_DELAY=0.5
   STREAM_MAX_FPS=20   # FPS RAW MJPEG потока
   INFER_FPS=5         # FPS инференса YOLO
   INFER_IMGSZ=416     # размер входа модели (320/384/416)
   ```

3. API потоков для интеграции/отладки:
   - `GET /api/detections/stream` — MJPEG с серверной разметкой
   - `GET /api/detections/stream-raw` — «чистый» MJPEG без разметки

### Проверка после деплоя

Запустите автотесты для проверки работоспособности:

```bash
# Проверка доступности сервисов
curl http://localhost:8001/health && echo "✅ Detection Service"
curl http://localhost:8080/health && echo "✅ Backend"
curl http://localhost && echo "✅ Frontend"
```

Скрипт проверит все эндпоинты, доступность сервисов и работоспособность Pi Camera.

Остановка:
```bash
docker compose down
```

## 5. Управление и диагностика

**Detection Service:**
- Логи: смотрите вывод в терминале или `sudo journalctl -u dc-detection -f`
- Проверка статуса: `curl http://localhost:8001/api/detection`
- Перезапуск: остановите через Ctrl+C и запустите снова

**Backend/Frontend:**
- Логи: `docker compose logs -f backend frontend`
- Очистить данные детекций: удалите файлы в `data/detections`
- Полный сброс: `docker compose down -v`

## 6. Частые вопросы

- **Где хранить модели?** В `services/detection/models/` (например, `yolov8n.pt`, `bestfire.pt`)
- **Как переключить модель?** Используйте API: `POST http://localhost:8001/models` с телом `{"name": "bestfire.pt"}`
- **Где сохраняются GIF?** В `data/detections/saved/YYYY-MM-DD/`. Доступ к gif: `/files/detections/saved/YYYY-MM-DD/<id>.gif`
- **Как сохранить клип?** Во вкладке «Список» нажмите «Сохранить» у нужной детекции (кадры берутся из буфера)
- **Где увидеть сохранённые?** Вкладка «Сохранённые» или `GET /api/detections/saved?date=YYYY-MM-DD`
- **Почему detection service запускается отдельно?** Для лучшей работы с камерой и доступа к устройствам без ограничений Docker


