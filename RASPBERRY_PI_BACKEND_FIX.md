# 🔧 Исправление ошибок подключения бэкенда на Raspberry Pi

## Проблема: Ошибка 503 "Cannot connect to detection service"

Если бэкенд выдает ошибки 503 при попытке подключиться к detection service, это означает, что бэкенд не может достучаться до `http://localhost:8001`.

## Решение

### Вариант 1: Использование network_mode: host (Рекомендуется для Raspberry Pi)

В `docker-compose.pi.yml` бэкенд настроен с `network_mode: host`, что позволяет ему обращаться к `localhost:8001` напрямую.

**Проверьте `.env` файл:**
```bash
DETECTION_URL=http://localhost:8001
```

### Вариант 2: Использование IP адреса хоста

Если `network_mode: host` не работает, используйте IP адрес Raspberry Pi:

1. Узнайте IP адрес:
```bash
hostname -I
# или
ip addr show | grep "inet " | grep -v 127.0.0.1
```

2. Установите в `.env`:
```bash
DETECTION_URL=http://192.168.0.50:8001  # Замените на ваш IP
```

### Вариант 3: Использование host.docker.internal

Если Docker поддерживает `host.docker.internal`:

```bash
DETECTION_URL=http://host.docker.internal:8001
```

## Проверка

1. Убедитесь, что detection service запущен:
```bash
curl http://localhost:8001/health
```

2. Проверьте, что бэкенд видит правильный URL:
```bash
# В логах бэкенда должно быть:
# Backend listening on :8080
# Detection Service URL: http://localhost:8001
```

3. Проверьте логи бэкенда:
```bash
sudo journalctl -u dc-detector -f
# или
docker compose logs backend -f
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

