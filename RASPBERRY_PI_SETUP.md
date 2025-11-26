# 🍓 Запуск Detection Service на Raspberry Pi

**Важно:** Detection Service запускается **отдельно от Docker** для лучшей работы с камерой. Это стандартный способ запуска.

Скрипт `detection_server.py` автоматически определяет доступную камеру и запускает видео поток.

### Шаг 1: Подготовка Raspberry Pi

1. Убедитесь, что у вас установлен Python 3:
   ```bash
   python3 --version
   ```

2. Установите необходимые системные пакеты:
   ```bash
   sudo apt update
   sudo apt install -y python3-picamera2 python3-pip python3-venv python3-full
   ```

3. **Важно:** На современных версиях Raspberry Pi OS (начиная с Debian 12) нельзя устанавливать пакеты глобально через `pip3` из-за защиты PEP 668. Используйте один из вариантов:

   **Вариант A: Виртуальное окружение (рекомендуется)**
   ```bash
   cd /path/to/DC-Detector
   python3 -m venv venv
   source venv/bin/activate
   cd services/detection
   pip install flask opencv-python ultralytics
   ```
   
   Или установите все зависимости из requirements.txt:
   ```bash
   cd /path/to/DC-Detector
   python3 -m venv venv
   source venv/bin/activate
   cd services/detection
   pip install -r requirements.txt
   ```
   
   **Важно:** Для детекции YOLO нужен `ultralytics`. Если его нет, детекция будет отключена, но видео поток будет работать.

   **Вариант B: Системные пакеты через apt (если доступны)**
   ```bash
   sudo apt install -y python3-flask python3-opencv
   ```
   
   **Вариант C: Использовать флаг --break-system-packages (не рекомендуется)**
   ```bash
   pip3 install --break-system-packages flask opencv-python
   ```

### Шаг 2: Запуск сервиса

1. Перейдите в директорию проекта:
   ```bash
   cd /path/to/DC-Detector/services/detection
   ```

2. Запустите скрипт:

   **Если используете виртуальное окружение:**
   ```bash
   source venv/bin/activate  # если еще не активировано
   cd services/detection
   python3 detection_server.py
   ```

   **Или используйте готовый скрипт (автоматически создаст и активирует venv):**
   ```bash
   cd services/detection && source ../../venv/bin/activate && python detection_server.py
   ```

### Шаг 3: Проверка работы

После запуска сервис автоматически:
- Попытается подключить **Picamera2** (если доступен)
- Если Picamera2 недоступен, попытается подключить **веб-камеру** через OpenCV
- Запустит Flask сервер на порту 8001

**Доступные эндпоинты:**
- Видео поток: `http://localhost:8001/video_feed_raw`
- Health check: `http://localhost:8001/health`
- Статус детекции: `http://localhost:8001/api/detection`
- Список трекеров: `http://localhost:8001/api/trackers`
- Управление моделями: `http://localhost:8001/models`

Откройте в браузере на Raspberry Pi или с другого устройства в локальной сети:
```
http://<IP-raspberry-pi>:8001/video_feed_raw
```

### Настройка порта

Вы можете изменить порт через переменную окружения:
```bash
PORT=8080 python3 detection_server.py
```

### Автозапуск при загрузке системы

Для автоматического запуска при загрузке Raspberry Pi используйте готовый скрипт:

```bash
sudo cp systemd/dc-detection.service /etc/systemd/system/
sudo cp systemd/dc-detector.service /etc/systemd/system/
sudo sed -i 's|/opt/dc-detector|/home/pi/dc-detector|g' /etc/systemd/system/*.service
sudo systemctl daemon-reload
sudo systemctl enable dc-detection.service dc-detector.service
```

Скрипт установит два systemd сервиса:
- `dc-detection.service` - Detection Service (запускается отдельно)
- `dc-detector.service` - Backend и Frontend (Docker Compose)

**Или установите вручную:**

1. Используйте готовый файл `systemd/dc-detection.service` и скопируйте его в `/etc/systemd/system/`, заменив пути:
   ```bash
   sudo cp systemd/dc-detection.service /etc/systemd/system/
   sudo sed -i "s|/opt/dc-detector|$(pwd)|g" /etc/systemd/system/dc-detection.service
   sudo sed -i "s|User=pi|User=$USER|g" /etc/systemd/system/dc-detection.service
   ```

2. Активируйте сервис:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable dc-detection
   sudo systemctl start dc-detection
   ```

3. Проверьте статус:
   ```bash
   sudo systemctl status dc-detection
   ```

4. Просмотр логов:
   ```bash
   sudo journalctl -u dc-detection -f
   ```

### Устранение проблем

**Проблема: Камера не определяется**

1. Проверьте, что камера подключена:
   ```bash
   lsusb  # для USB камер
   vcgencmd get_camera  # для Pi Camera (должно вернуть supported=1 detected=1)
   ```

2. Проверьте доступ к камере:
   ```bash
   ls -l /dev/video*
   ```

3. Для Pi Camera убедитесь, что камера включена:
   ```bash
   sudo raspi-config
   # Интерфейсы -> Камера -> Включить
   ```

**Проблема: Ошибка "ModuleNotFoundError: No module named 'picamera2'"**

Установите picamera2:
```bash
sudo apt install python3-picamera2
```

**Проблема: Ошибка "ModuleNotFoundError: No module named 'cv2'"**

Установите OpenCV в виртуальное окружение:
```bash
source venv/bin/activate
pip install opencv-python
```

Или через системные пакеты:
```bash
sudo apt install python3-opencv
```

**Проблема: Ошибка "externally-managed-environment" при установке через pip3**

Это нормальная защита в современных версиях Raspberry Pi OS. Используйте виртуальное окружение:
```bash
python3 -m venv venv
source venv/bin/activate
pip install flask opencv-python
```

**Проблема: Порт уже занят**

Измените порт через переменную окружения:
```bash
PORT=8080 python3 detection_server.py
```

Или остановите процесс, использующий порт 8001:
```bash
sudo lsof -i :8001
sudo kill <PID>
```

### Интеграция с остальными сервисами

Detection Service запускается отдельно, а Backend и Frontend в Docker:

1. В `.env` настройте `DETECTION_URL`:
   ```dotenv
   DETECTION_URL=http://localhost:8001
   ```

2. Backend автоматически подключится к Detection Service по указанному URL.

3. Если Detection Service запущен на другом хосте, укажите его IP:
   ```dotenv
   DETECTION_URL=http://192.168.1.100:8001
   ```

### Производительность

Для оптимизации FPS на Raspberry Pi:

1. Используйте Pi Camera вместо USB камеры (лучшая производительность)
2. Уменьшите разрешение в коде (по умолчанию 1280x720)
3. Настройте FPS в коде (по умолчанию ~30 FPS)

Для изменения разрешения отредактируйте `detection_server.py`:
- В `init_picamera2()`: измените `main={"size": (1280, 720)}`
- В `init_webcam()`: измените `cv2.CAP_PROP_FRAME_WIDTH` и `cv2.CAP_PROP_FRAME_HEIGHT`

