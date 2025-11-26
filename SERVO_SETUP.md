# 🔧 Настройка сервоприводов для слежения за объектами

Система поддерживает два способа подключения сервоприводов для управления камерой (pan/tilt):

## 📋 Варианты подключения

### 1. Прямое подключение через GPIO (Raspberry Pi)

**Подходит для:** 2 сервопривода, подключенных напрямую к GPIO пинам Raspberry Pi

**Требования:**
- Raspberry Pi
- 2 сервопривода (SG90 или аналогичные)
- Библиотека: `RPi.GPIO`

**Подключение:**
- **Pan серво** (горизонтальное вращение): подключить к GPIO пин (по умолчанию 18)
  - Красный провод (VCC) → 5V (пин 2 или 4)
  - Коричневый/черный (GND) → GND (пин 6, 9, 14, 20, 25, 30, 34, 39)
  - Оранжевый/желтый (Signal) → GPIO 18 (пин 12)
  
- **Tilt серво** (вертикальное вращение): подключить к GPIO пин (по умолчанию 19)
  - Красный провод (VCC) → 5V
  - Коричневый/черный (GND) → GND
  - Оранжевый/желтый (Signal) → GPIO 19 (пин 35)

**Настройка через переменные окружения:**
```bash
export SERVO_HARDWARE=gpio
export SERVO_PAN_PIN=18      # GPIO пин для pan серво
export SERVO_TILT_PIN=19     # GPIO пин для tilt серво
export SERVO_FREQUENCY=50    # Частота PWM (50Hz для стандартных сервоприводов)
```

**Установка зависимости:**
```bash
pip install RPi.GPIO
```

### 2. Подключение через PCA9685 (I2C PWM контроллер)

**Подходит для:** Множество сервоприводов, более стабильная работа, нет конфликтов с GPIO

**Требования:**
- PCA9685 модуль (16-канальный PWM контроллер)
- Подключение через I2C
- Библиотека: `adafruit-circuitpython-servokit`

**Подключение:**
- PCA9685 подключается к Raspberry Pi через I2C:
  - VCC → 3.3V или 5V
  - GND → GND
  - SDA → GPIO 2 (SDA)
  - SCL → GPIO 3 (SCL)

- Сервоприводы подключаются к PCA9685:
  - **Pan серво** → канал 0 (по умолчанию)
  - **Tilt серво** → канал 1 (по умолчанию)
  - VCC сервоприводов → V+ на PCA9685 (внешнее питание 5V рекомендуется)
  - GND → GND на PCA9685
  - Signal → соответствующий канал (0-15)

**Настройка через переменные окружения:**
```bash
export SERVO_HARDWARE=pca9685
export SERVO_PAN_CHANNEL=0      # Канал PCA9685 для pan серво (0-15)
export SERVO_TILT_CHANNEL=1     # Канал PCA9685 для tilt серво (0-15)
export SERVO_PCA9685_ADDRESS=0x40  # I2C адрес PCA9685 (обычно 0x40)
export SERVO_FREQUENCY=50       # Частота PWM (50Hz)
```

**Установка зависимости:**
```bash
pip install adafruit-circuitpython-servokit
```

**Включение I2C на Raspberry Pi:**
```bash
sudo raspi-config
# Interface Options → I2C → Enable
sudo reboot
```

### 3. Программный режим (без железа)

**Подходит для:** Разработка и тестирование без реальных сервоприводов

**Настройка:**
```bash
export SERVO_HARDWARE=none
# или просто не устанавливать переменную
```

В этом режиме углы сервоприводов только логируются, реальное железо не используется.

## 🚀 Быстрый старт

### Для GPIO (2 сервопривода):

1. Подключите сервоприводы к GPIO пинам
2. Установите зависимость:
   ```bash
   pip install RPi.GPIO
   ```
3. Настройте переменные окружения:
   ```bash
   export SERVO_HARDWARE=gpio
   export SERVO_PAN_PIN=18
   export SERVO_TILT_PIN=19
   ```
4. Запустите detection service:
   ```bash
   python detection_server.py
   ```

### Для PCA9685:

1. Подключите PCA9685 к Raspberry Pi через I2C
2. Подключите сервоприводы к каналам PCA9685
3. Установите зависимость:
   ```bash
   pip install adafruit-circuitpython-servokit
   ```
4. Включите I2C (если еще не включен)
5. Настройте переменные окружения:
   ```bash
   export SERVO_HARDWARE=pca9685
   export SERVO_PAN_CHANNEL=0
   export SERVO_TILT_CHANNEL=1
   ```
6. Запустите detection service

## ⚙️ Настройка в systemd service

Добавьте переменные окружения в `systemd/dc-detection.service`:

```ini
[Service]
Environment="SERVO_HARDWARE=gpio"
Environment="SERVO_PAN_PIN=18"
Environment="SERVO_TILT_PIN=19"
Environment="SERVO_FREQUENCY=50"
```

Или для PCA9685:

```ini
[Service]
Environment="SERVO_HARDWARE=pca9685"
Environment="SERVO_PAN_CHANNEL=0"
Environment="SERVO_TILT_CHANNEL=1"
Environment="SERVO_PCA9685_ADDRESS=0x40"
```

## 🔍 Проверка работы

После запуска detection service проверьте логи:
```bash
journalctl -u dc-detection -f
```

Должны появиться сообщения:
- `GPIO Servo initialized: pan_pin=18, tilt_pin=19, freq=50Hz` (для GPIO)
- `PCA9685 Servo initialized: pan_channel=0, tilt_channel=1, ...` (для PCA9685)

При обнаружении объекта и установке целевого трекера сервоприводы должны автоматически поворачивать камеру для слежения.

## 📝 Примечания

- **Питание:** Сервоприводы потребляют много тока. Для 2 сервоприводов через GPIO может потребоваться внешний источник питания 5V.
- **PCA9685 рекомендуется** для более стабильной работы и возможности подключения большего количества сервоприводов.
- **Углы:** Сервоприводы работают в диапазоне 0-180 градусов. Центральная позиция = 90°.
- **Частота:** Стандартные сервоприводы работают на 50Hz. Некоторые модели могут требовать другую частоту.

## 🛠️ Устранение неполадок

**Сервоприводы не двигаются:**
- Проверьте подключение проводов
- Убедитесь, что установлена нужная библиотека
- Проверьте логи на наличие ошибок инициализации
- Для PCA9685: проверьте I2C подключение (`i2cdetect -y 1`)

**Сервоприводы дергаются:**
- Проверьте питание (может не хватать тока)
- Уменьшите чувствительность в коде (параметр `_step`)

**Ошибка "RPi.GPIO not available":**
- Убедитесь, что код запускается на Raspberry Pi
- Установите библиотеку: `pip install RPi.GPIO`

