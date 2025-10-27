FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    cmake \
    pkg-config \
    python3-dev \
    libgl1 \
    libglib2.0-0t64 \
    libsm6 \
    libxext6 \
    libgomp1 \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копирование и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование приложения
COPY camera_server.py .

# Открытие порта
EXPOSE 8000

# Переменные окружения
ENV PYTHONUNBUFFERED=1

# Запуск
CMD ["python", "camera_server.py"]

