FROM python:3.11-slim-bullseye
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=180 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender1 ffmpeg curl \
 && rm -rf /var/lib/apt/lists/*

# Попытка установить Raspberry Pi специфичные пакеты (доступны только на Raspberry Pi OS)
# Если пакеты недоступны, сборка продолжается без них
RUN apt-get update && \
    (apt-get install -y --no-install-recommends \
        libcamera-dev \
        python3-picamera2 \
    2>&1 || echo "⚠️ libcamera-dev и python3-picamera2 недоступны (не Raspberry Pi OS)") && \
    rm -rf /var/lib/apt/lists/*

# Добавляем пользователя в группу video для доступа к камере
RUN usermod -a -G video root || echo "⚠️ Не удалось добавить в группу video"

# Проверяем доступность picamera2
RUN python3 -c "import picamera2; print('✅ picamera2 доступен')" 2>&1 || echo "⚠️ picamera2 не может быть импортирован (это нормально, если не на Raspberry Pi)"

COPY services/detection/requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY services/detection ./

EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD curl -fsS http://localhost:8001/health || exit 1
CMD ["python", "detection_server.py"]


