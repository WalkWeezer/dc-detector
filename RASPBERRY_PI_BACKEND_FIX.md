# 🔧 Исправление ошибок подключения бэкенда на Raspberry Pi

## Проблемы подключения бэкенда на Raspberry Pi

### Проблема 1: Ошибка 503 "Cannot connect to detection service"

Если бэкенд выдает ошибки 503 при попытке подключиться к detection service, это означает, что бэкенд не может достучаться до `http://localhost:8001`.

### Проблема 2: Ошибка "mutually exclusive network_mode and networks"

Если при запуске Docker Compose возникает ошибка:
```
service backend declares mutually exclusive 'network_mode' and 'networks': invalid compose project
```

Это означает конфликт между `network_mode: host` и `networks` в объединенных файлах Docker Compose.

## Решение

### Вариант 1: Использование network_mode: host (Рекомендуется для Raspberry Pi)

**Если возникает ошибка "mutually exclusive network_mode and networks"**, используйте полностью независимый compose файл:

```bash
# Используйте standalone файл вместо объединения с docker-compose.yml
docker compose -f docker-compose.pi-standalone.yml up -d --build
```

Этот файл не объединяется с базовым `docker-compose.yml`, поэтому конфликта не будет.

**Проверьте `.env` файл:**
```bash
DETECTION_URL=http://localhost:8001
```

**Альтернатива:** Если хотите использовать объединение файлов, используйте `docker-compose.pi-alt.yml` (см. Вариант 2).

### Вариант 2: Использование IP адреса хоста (Альтернатива при конфликте network_mode)

Если `network_mode: host` вызывает конфликт с `networks`, используйте IP адрес хоста:

1. Узнайте IP адрес хоста из контейнера:
```bash
# IP адрес Docker bridge (обычно 172.17.0.1)
ip addr show docker0 | grep "inet " | awk '{print $2}' | cut -d/ -f1

# Или IP адрес Raspberry Pi в локальной сети
hostname -I | awk '{print $1}'
```

2. Используйте `docker-compose.pi-alt.yml` вместо `docker-compose.pi.yml`:
```bash
docker compose -f docker-compose.yml -f docker-compose.pi-alt.yml up -d --build
```

3. Установите в `.env`:
```bash
# Используйте IP Docker bridge (172.17.0.1) или IP Raspberry Pi в сети
DETECTION_URL=http://172.17.0.1:8001
# или
DETECTION_URL=http://192.168.1.100:8001  # Замените на IP Raspberry Pi
```

### Вариант 3: Использование host.docker.internal

Если Docker поддерживает `host.docker.internal`:

```bash
DETECTION_URL=http://host.docker.internal:8001
```

## Важно: Очистка старых контейнеров

Если контейнеры были запущены со старым способом (объединение файлов), их нужно остановить и удалить:

```bash
# Остановить и удалить все контейнеры
docker compose -f docker-compose.yml -f docker-compose.pi.yml down

# Или если они уже запущены, принудительно удалить
docker compose -f docker-compose.yml -f docker-compose.pi.yml down --remove-orphans

# Теперь запустить с новым standalone файлом
docker compose -f docker-compose.pi-standalone.yml up -d --build
```

## Проверка

1. Убедитесь, что файл `docker-compose.pi-standalone.yml` существует:
```bash
ls -la docker-compose.pi-standalone.yml
```

2. Убедитесь, что detection service запущен:
```bash
curl http://localhost:8001/health
```

3. Проверьте, что бэкенд видит правильный URL:
```bash
# В логах бэкенда должно быть:
# Backend listening on :8080
# Detection Service URL: http://localhost:8001
```

4. Проверьте логи бэкенда:
```bash
sudo journalctl -u dc-detector -f
# или
docker compose -f docker-compose.pi-standalone.yml logs backend -f
```

## Частые проблемы

### "Cannot connect to detection service at http://detection:8001"

**Проблема:** В `.env` указан неправильный URL `http://detection:8001`

**Решение:** Измените в `.env`:
```bash
DETECTION_URL=http://localhost:8001
```

### "Connection refused"

**Проблема:** Detection service не запущен или недоступен

**Решение:**
1. Проверьте, запущен ли detection service:
```bash
ps aux | grep detection_server
```

2. Если не запущен, запустите:
```bash
cd services/detection
source ../../venv/bin/activate
python detection_server.py
```

3. Проверьте доступность:
```bash
curl http://localhost:8001/health
```

### "ENOTFOUND" или "getaddrinfo failed"

**Проблема:** Неправильный hostname в DETECTION_URL

**Решение:** Используйте IP адрес вместо hostname:
```bash
DETECTION_URL=http://192.168.0.50:8001
```

## Быстрая диагностика

Выполните на Raspberry Pi:

```bash
#!/bin/bash
echo "=== Диагностика подключения бэкенда ==="

# 1. Проверка detection service
echo "1. Проверка detection service..."
curl -s http://localhost:8001/health || echo "❌ Detection service недоступен"

# 2. Проверка .env
echo "2. Проверка DETECTION_URL в .env..."
if [ -f .env ]; then
  grep DETECTION_URL .env || echo "⚠️  DETECTION_URL не найден в .env"
else
  echo "❌ .env файл не найден"
fi

# 3. Проверка бэкенда
echo "3. Проверка бэкенда..."
curl -s http://localhost:8080/health || echo "❌ Backend недоступен"

# 4. Проверка логов
echo "4. Последние логи бэкенда:"
sudo journalctl -u dc-detector -n 20 --no-pager | tail -10

echo "=== Диагностика завершена ==="
```

## После исправления

1. Перезапустите бэкенд:
```bash
sudo systemctl restart dc-detector
```

2. Проверьте логи:
```bash
sudo journalctl -u dc-detector -f
```

3. Проверьте API:
```bash
curl http://localhost:8080/api/detection
curl http://localhost:8080/api/trackers
```

