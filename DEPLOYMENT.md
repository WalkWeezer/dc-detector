# 🚀 Руководство по деплою DC-Detector

## Обзор

DC-Detector состоит из трех основных компонентов:
1. **Detection Service** - Python сервис для детекции объектов (порт 8001)
2. **Backend** - Node.js API сервер (порт 8080)
3. **Frontend** - Nginx веб-интерфейс (порт 80)

## Быстрый старт

### Raspberry Pi (Production)

```bash
# Полный деплой (остановка + запуск)
./scripts/deploy.sh prod deploy

# Или используйте отдельные скрипты
./scripts/start-prod.sh  # Запуск
./scripts/stop-prod.sh   # Остановка
```

### Development

```bash
# Используйте docker-compose.dev.yml
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## Структура Docker Compose файлов

Проект использует систему приоритетов для выбора compose файлов:

1. **docker-compose.prod.yml** (production)
   - Полностью независимый файл для production (Raspberry Pi)
   - Использует `network_mode: host` для backend
   - Избегает конфликта `network_mode`/`networks`

2. **docker-compose.dev.yml** (development)
   - Override файл для разработки
   - Объединяется с `docker-compose.yml`
   - Добавляет hot-reload и dev режимы

3. **docker-compose.yml**
   - Базовый файл для всех окружений

### Автоматический выбор файлов

Все скрипты используют `scripts/compose-helper.sh` для автоматического выбора правильного compose файла:

```bash
source scripts/compose-helper.sh
COMPOSE_ARGS=$(get_compose_files "$PROJECT_ROOT")
docker compose $COMPOSE_ARGS up -d
```

## Скрипты деплоя

### `scripts/deploy.sh` - Единый скрипт деплоя

```bash
# Синтаксис
./scripts/deploy.sh [ENV] [ACTION]

# Примеры
./scripts/deploy.sh prod deploy   # Production деплой
./scripts/deploy.sh prod start    # Только запуск
./scripts/deploy.sh prod stop     # Только остановка
./scripts/deploy.sh prod restart # Перезапуск
./scripts/deploy.sh prod status   # Статус сервисов
./scripts/deploy.sh prod logs     # Логи сервисов
```

### `scripts/start-prod.sh` - Запуск production

Выполняет:
1. Проверку системных зависимостей
2. Настройку Python venv (с `--system-site-packages` для picamera2)
3. Установку недостающих пакетов
4. Запуск Detection Service
5. Запуск Docker сервисов (Backend + Frontend)

### `scripts/stop-prod.sh` - Остановка production

Выполняет:
1. Остановку Detection Service
2. Остановку Docker контейнеров

### `scripts/compose-helper.sh` - Утилита выбора compose файлов

Используется всеми скриптами для единообразного выбора compose файлов.

## Systemd сервисы

### Установка

```bash
sudo ./scripts/install-systemd.sh
```

Это установит два сервиса:
- `dc-detection.service` - Detection Service
- `dc-detector.service` - Backend + Frontend (Docker)

### Управление

```bash
# Detection Service
sudo systemctl start dc-detection
sudo systemctl stop dc-detection
sudo systemctl status dc-detection
sudo journalctl -u dc-detection -f

# Backend/Frontend (Docker)
sudo systemctl start dc-detector
sudo systemctl stop dc-detector
sudo systemctl status dc-detector
sudo journalctl -u dc-detector -f
```

## Конфигурация

### Переменные окружения

Создайте `.env` файл на основе `env.example`:

```bash
cp env.example .env
```

Важные переменные:
- `DETECTION_URL` - URL detection service (для backend)
  - Raspberry Pi: `http://localhost:8001`
  - Docker: `http://host.docker.internal:8001` или IP адрес

### Docker Compose переменные

В `docker-compose.yml` и `docker-compose.prod.yml`:
- `PORT` - Порт backend (по умолчанию 8080)
- `DETECTION_URL` - URL detection service

## Устранение проблем

### Ошибка "mutually exclusive network_mode and networks"

**Причина:** Конфликт между `network_mode: host` и `networks` при объединении файлов.

**Решение:** Используйте `docker-compose.prod.yml`:

```bash
# Убедитесь, что файл существует
ls -la docker-compose.prod.yml

# Остановите старые контейнеры
docker compose down --remove-orphans

# Запустите с prod файлом
docker compose -f docker-compose.prod.yml up -d --build
```

### Detection Service не запускается

1. Проверьте Python venv:
```bash
source venv/bin/activate
python -c "import picamera2"
```

2. Проверьте логи:
```bash
tail -f .detection.log
```

3. Запустите вручную:
```bash
cd services/detection
source ../../venv/bin/activate
python detection_server.py
```

### Backend не может подключиться к Detection Service

1. Проверьте, что Detection Service запущен:
```bash
curl http://localhost:8001/health
```

2. Проверьте `DETECTION_URL` в `.env`:
```bash
grep DETECTION_URL .env
```

3. Для Raspberry Pi с `network_mode: host`:
```bash
DETECTION_URL=http://localhost:8001
```

4. Для Docker без `network_mode: host`:
```bash
# Узнайте IP Docker bridge
ip addr show docker0 | grep "inet " | awk '{print $2}' | cut -d/ -f1

# Или используйте IP Raspberry Pi
hostname -I | awk '{print $1}'
```

## Тестирование деплоя

Проверьте доступность сервисов:

```bash
# Проверка всех сервисов
curl http://localhost:8001/health && echo "✅ Detection Service"
curl http://localhost:8080/health && echo "✅ Backend"
curl http://localhost && echo "✅ Frontend"
```

## Обновление

```bash
# 1. Остановите сервисы
./scripts/stop-prod.sh

# 2. Обновите код
git pull

# 3. Запустите заново
./scripts/start-prod.sh

# Или используйте единый скрипт
./scripts/deploy.sh prod restart
```

## Мониторинг

### Логи

```bash
# Detection Service
tail -f .detection.log

# Docker сервисы
docker compose -f docker-compose.prod.yml logs -f

# Или через systemd
sudo journalctl -u dc-detection -f
sudo journalctl -u dc-detector -f
```

### Статус

```bash
# Через deploy скрипт
./scripts/deploy.sh prod status

# Или вручную
docker compose -f docker-compose.prod.yml ps
ps aux | grep detection_server
```

## Архитектура

```
┌─────────────────┐
│   Frontend      │  Port 80 (Nginx)
│   (Docker)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Backend        │  Port 8080 (Node.js)
│   (Docker)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Detection       │  Port 8001 (Python)
│ Service         │
│ (Host Process)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Camera        │  /dev/video0
│   (Hardware)    │
└─────────────────┘
```

## Дополнительные ресурсы

- [RASPBERRY_PI_BACKEND_FIX.md](RASPBERRY_PI_BACKEND_FIX.md) - Устранение проблем на Raspberry Pi
- [README.md](README.md) - Общая документация проекта

