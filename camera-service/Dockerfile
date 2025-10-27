FROM python:3.11-slim

# Установка системных зависимостей с retry
RUN apt-get update || apt-get update || apt-get update && \
    apt-get install -y --no-install-recommends \
    python3-dev \
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

