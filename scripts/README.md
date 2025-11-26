# Скрипты запуска системы DC-Detector

## 🖥️ Для разработки на Windows/ПК

### Запуск всех сервисов

```powershell
.\scripts\start-dev.ps1
```

**Что делает скрипт:**
- ✅ Проверяет зависимости (Python, Node.js)
- ✅ Устанавливает недостающие пакеты
- ✅ Запускает Detection Service (порт 8001)
- ✅ Запускает Backend (порт 8080)
- ✅ Запускает Frontend через Vite (порт 5173)

**Доступные сервисы после запуска:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8080
- Detection Service: http://localhost:8001

### Остановка всех сервисов

```powershell
.\scripts\stop-dev.ps1
```

Или нажмите `Ctrl+C` в окне, где запущен `start-dev.ps1`.

**Логи процессов:**
- Detection Service: `.detection-output.log`
- Backend: `.backend-output.log`
- Frontend: `.frontend-output.log`

## 🍓 Для продакшна на Raspberry Pi

### Запуск всех сервисов

```bash
chmod +x scripts/start-prod.sh
./scripts/start-prod.sh
```

**Что делает скрипт:**
- ✅ Проверяет зависимости (Python, Docker, Docker Compose)
- ✅ Создает виртуальное окружение если нужно
- ✅ Устанавливает недостающие пакеты
- ✅ Запускает Detection Service в фоне (порт 8001)
- ✅ Запускает Backend и Frontend через Docker (порты 8080 и 80)

**Доступные сервисы после запуска:**
- Frontend: http://localhost (или IP адрес Raspberry Pi)
- Backend API: http://localhost:8080
- Detection Service: http://localhost:8001

### Остановка всех сервисов

```bash
chmod +x scripts/stop-prod.sh
./scripts/stop-prod.sh
```

**Логи:**
- Detection Service: `.detection.log`
- Docker контейнеры: `docker compose logs -f`

## 📋 Требования

### Для разработки (Windows/ПК):
- Python 3.11+
- Node.js 20+
- npm (устанавливается с Node.js)

### Для продакшна (Raspberry Pi):
- Python 3.11+
- Docker 24+
- Docker Compose v2
- (Опционально) picamera2 для работы с камерой Raspberry Pi

## 🔧 Устранение неполадок

### Порт уже занят

**Windows:**
```powershell
# Найти процесс на порту
netstat -ano | findstr :8001

# Остановить процесс
Stop-Process -Id <PID> -Force
```

**Linux/Raspberry Pi:**
```bash
# Найти процесс на порту
lsof -i :8001

# Остановить процесс
kill <PID>
```

### Зависимости не установлены

Скрипты автоматически проверяют и устанавливают зависимости, но если что-то пошло не так:

**Detection Service:**
```bash
cd services/detection
pip install -r requirements.txt
```

**Backend:**
```bash
cd services/backend
npm install
```

**Frontend:**
```bash
cd frontend
npm install
```

### Процессы не останавливаются

Если `stop-dev.ps1` или `stop-prod.sh` не останавливают процессы:

**Windows:**
```powershell
# Остановить все процессы по портам
Get-NetTCPConnection -LocalPort 8001,8080,5173 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

**Linux/Raspberry Pi:**
```bash
# Остановить все процессы по портам
lsof -ti:8001 | xargs kill -9
lsof -ti:8080 | xargs kill -9
lsof -ti:80 | xargs kill -9
```





