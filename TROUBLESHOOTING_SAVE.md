# 🔧 Устранение ошибки сохранения детекций на Raspberry Pi

## Проблема: Ошибка 500 при сохранении детекций

Если при сохранении детекции возникает ошибка 500, проверьте следующие моменты:

## 1. Проверка прав доступа к директории

Убедитесь, что у процесса бэкенда есть права на запись в директорию `data/detections/saved/`:

```bash
# Проверьте текущие права
ls -la data/detections/saved/

# Если нужно, установите права
sudo chown -R pi:pi data/detections/
chmod -R 755 data/detections/
```

## 2. Проверка установки зависимостей

Убедитесь, что все зависимости установлены, особенно `sharp`:

```bash
cd services/backend
npm list sharp gif-encoder-2 jpeg-js
```

Если `sharp` не установлен или установлен неправильно:

```bash
# Переустановите sharp (может потребоваться время на компиляцию)
npm uninstall sharp
npm install sharp

# Или для Raspberry Pi может потребоваться:
npm install --platform=linux --arch=arm64 sharp
```

## 3. Проверка логов бэкенда

Проверьте логи бэкенда для детальной информации об ошибке:

```bash
# Если используется systemd
sudo journalctl -u dc-detector -f

# Или если запущен вручную
# Смотрите вывод в консоли
```

Ищите сообщения типа:
- `Error in saveUserDetection`
- `Failed to create saved directory`
- `Image processing failed`
- `No write permission`

## 4. Проверка доступности detection service

Убедитесь, что detection service доступен и возвращает кадры:

```bash
# Проверка статуса
curl http://localhost:8001/health

# Проверка трекеров
curl http://localhost:8001/api/trackers

# Проверка кадров для трекера (замените 1 на реальный trackId)
curl http://localhost:8001/api/trackers/1/frames
```

## 5. Проверка памяти

На Raspberry Pi может не хватать памяти для обработки изображений. Проверьте:

```bash
free -h
```

Если памяти мало (< 100MB свободно), попробуйте:
- Уменьшить количество кадров в GIF (в коде)
- Увеличить swap
- Закрыть другие приложения

## 6. Проверка формата данных

Убедитесь, что фронтенд отправляет данные в правильном формате:

```javascript
// Правильный формат:
{
  trackId: 123,
  name: "optional name"
}

// Или:
{
  detection: { ... },
  frames: ["data:image/jpeg;base64,...", ...],
  fps: 5
}
```

## 7. Временное решение: Упрощенное сохранение

Если проблема сохраняется, можно временно отключить создание GIF и сохранять только JSON:

В `services/backend/src/storage/detectionsStore.js` можно добавить флаг для отключения GIF:

```javascript
const SKIP_GIF = process.env.SKIP_GIF === 'true'

if (!SKIP_GIF) {
  // ... код создания GIF
}
```

## 8. Проверка переменных окружения

Убедитесь, что переменные окружения установлены правильно:

```bash
echo $DETECTIONS_DIR
echo $DETECTION_URL
```

## Быстрая диагностика

Выполните этот скрипт для проверки:

```bash
#!/bin/bash
echo "=== Проверка сохранения детекций ==="

# 1. Права доступа
echo "1. Проверка прав доступа..."
ls -la data/detections/saved/ 2>/dev/null || echo "Директория не существует"

# 2. Зависимости
echo "2. Проверка зависимостей..."
cd services/backend
npm list sharp gif-encoder-2 jpeg-js 2>/dev/null | grep -E "sharp|gif-encoder|jpeg-js"

# 3. Detection service
echo "3. Проверка detection service..."
curl -s http://localhost:8001/health | head -1

# 4. Backend
echo "4. Проверка backend..."
curl -s http://localhost:8080/health | head -1

# 5. Память
echo "5. Свободная память:"
free -h | grep Mem

echo "=== Проверка завершена ==="
```

## Частые ошибки и решения

### "No write permission"
```bash
sudo chown -R pi:pi data/
chmod -R 755 data/
```

### "sharp: invalid input"
- Проверьте формат данных frames (должны быть base64 data URLs)
- Убедитесь, что sharp установлен для правильной архитектуры

### "no valid frames"
- Проверьте, что detection service возвращает кадры
- Убедитесь, что trackId существует и активен

### "Failed to create saved directory"
- Проверьте права на родительскую директорию
- Убедитесь, что достаточно места на диске: `df -h`

