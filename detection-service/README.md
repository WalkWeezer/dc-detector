# 🔥 Detection Service

Сервис детекции огня на базе YOLO для анализа видеопотока от camera-service.

## ⚠️ Важно для Raspberry Pi

Установка PyTorch на Raspberry Pi требует специальных действий, так как официальные wheels могут быть недоступны.

### Шаг 1: Определите архитектуру системы

```bash
uname -m
```

- `aarch64` или `arm64` = 64-bit система
- `armv7l` или `armhf` = 32-bit система

### Шаг 2: Установка PyTorch

#### Для ARM64 (64-bit OS) - Raspberry Pi 4/5 с 64-bit OS:

**Вариант 1: Попробуйте официальные wheels (может не работать):**
```bash
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

**Вариант 2: Используйте piwheels (рекомендуется):**
```bash
pip3 install --upgrade pip
pip3 install torch torchvision
```

**Вариант 3: Установите через apt (если доступно):**
```bash
sudo apt-get update
sudo apt-get install python3-pytorch python3-torchvision
```

#### Для ARM32 (32-bit OS) - Raspberry Pi с 32-bit OS:

**Вариант 1: Используйте pre-built wheels от сообщества:**
```bash
pip3 install --upgrade pip
pip3 install torch==1.13.0 torchvision==0.14.0 --index-url https://download.pytorch.org/whl/cpu
```

**Вариант 2: Используйте piwheels:**
```bash
pip3 install --upgrade pip
pip3 install torch torchvision
```

**Вариант 3: Установите минимальную версию:**
```bash
pip3 install torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu
```

**Вариант 4: Компиляция из исходников (долго, но надежно):**
```bash
# Требует много времени (4-6 часов) и места (2-3GB)
sudo apt-get install libopenblas-dev libblas-dev libatlas-base-dev liblapack-dev
pip3 install torch torchvision --no-binary torch,torchvision
```

### Шаг 3: Установите ultralytics

После успешной установки PyTorch:
```bash
pip3 install ultralytics
```

### Решение проблем

Если установка не удается:

1. **Проверьте версию Python:**
   ```bash
   python3 --version
   ```
   Рекомендуется Python 3.8-3.11.

2. **Обновите pip и установите зависимости:**
   ```bash
   pip3 install --upgrade pip setuptools wheel
   sudo apt-get install python3-dev
   ```

3. **Попробуйте установить конкретные версии:**
   ```bash
   pip3 install torch==2.0.0 torchvision==0.15.0
   ```

4. **Альтернатива: Используйте ONNX Runtime вместо PyTorch** (требует модификации кода)

## Возможности

- 🔍 Детекция огня в реальном времени
- 🎥 Анализ видеопотока от camera-service
- 📊 REST API для получения результатов
- 🎨 Визуализация детекций на кадрах
- ⚠️ Уведомления о обнаружении

## Быстрый запуск

### Требования

1. Запущенный camera-service на порту 8000
2. Модель YOLO в корне проекта (`bestfire.pt`)

### Установка и запуск

#### На обычном компьютере

```bash
cd detection-service
pip3 install -r requirements.txt
python3 detection_server.py
```

#### На Raspberry Pi (с предустановленным PyTorch)

```bash
cd detection-service
pip3 install flask opencv-python numpy requests
python3 detection_server.py
```

Сервис будет доступен по адресу: http://localhost:8001

## API Endpoints

- `GET /` - Веб-интерфейс с результатами детекции
- `GET /api/detection` - JSON статус детекции
- `GET /detection_frame` - Последний кадр с детекциями (MJPEG)
- `GET /health` - Health check

## Примеры использования

### Проверка статуса

```bash
curl http://localhost:8001/api/detection
```

Ответ:
```json
{
  "detected": true,
  "count": 2,
  "confidence": 0.87,
  "last_detection": 1698405000.0,
  "detections": [
    {
      "bbox": [100.0, 150.0, 250.0, 300.0],
      "confidence": 0.87,
      "class_id": 0
    }
  ]
}
```

### Получение кадра с детекциями

```bash
curl http://localhost:8001/detection_frame -o detection.jpg
```

## Настройки

В `detection_server.py` можно изменить:

- `CAMERA_SERVICE_URL` - URL сервиса камеры
- `MODEL_PATH` - Путь к модели YOLO
- `CONFIDENCE_THRESHOLD` - Порог уверенности детекции (по умолчанию 0.5)

## Архитектура

```
camera-service (8000) → detection-service (8001)
     ↓                         ↓
  Video Feed              YOLO Model
                           Detection
                             ↓
                      Detection Results
```

## Использование в других сервисах

Сервис детекции можно использовать в других компонентах системы:

```python
import requests

response = requests.get('http://localhost:8001/api/detection')
data = response.json()

if data['detected']:
    print(f"🔥 Обнаружен огонь! {data['count']} объектов")
    # Отправить уведомление, сохранить видео и т.д.
```

## Остановка

Нажмите `Ctrl+C` в терминале, где запущен сервис.

