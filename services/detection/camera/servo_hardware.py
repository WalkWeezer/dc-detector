"""Hardware implementations for servo control."""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class HardwareServoController:
    """Base class for hardware servo controllers."""

    def __init__(self, pan_pin: Optional[int] = None, tilt_pin: Optional[int] = None):
        self.pan_pin = pan_pin
        self.tilt_pin = tilt_pin
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize hardware. Returns True if successful."""
        raise NotImplementedError

    def set_angle(self, servo: str, angle: float) -> None:
        """Set angle for servo (pan or tilt). Angle in degrees (0-180)."""
        raise NotImplementedError

    def cleanup(self) -> None:
        """Cleanup hardware resources."""
        raise NotImplementedError

    def is_available(self) -> bool:
        """Check if hardware is available."""
        return self._initialized


class GPIOServoController(HardwareServoController):
    """Servo controller using RPi.GPIO for direct GPIO control.
    
    Requires: pip install RPi.GPIO
    Suitable for: Raspberry Pi with servos connected directly to GPIO pins
    """

    def __init__(self, pan_pin: int = 18, tilt_pin: int = 19, frequency: int = 50):
        """
        Args:
            pan_pin: GPIO pin number for pan servo (default: 18)
            tilt_pin: GPIO pin number for tilt servo (default: 19)
            frequency: PWM frequency in Hz (default: 50 for standard servos)
        """
        super().__init__(pan_pin, tilt_pin)
        self.frequency = frequency
        self.pan_pwm = None
        self.tilt_pwm = None
        self._gpio = None

    def initialize(self) -> bool:
        """Initialize GPIO and PWM."""
        print(f"🔌 [SERVO-GPIO] Инициализация GPIO сервоприводов...")
        print(f"   [SERVO-GPIO] Pan pin: {self.pan_pin}")
        print(f"   [SERVO-GPIO] Tilt pin: {self.tilt_pin}")
        print(f"   [SERVO-GPIO] Frequency: {self.frequency} Hz")
        logger.info("🔌 Инициализация GPIO сервоприводов...")
        logger.info("   Pan pin: %d", self.pan_pin)
        logger.info("   Tilt pin: %d", self.tilt_pin)
        logger.info("   Frequency: %d Hz", self.frequency)
        
        try:
            import RPi.GPIO as GPIO
            print("✅ [SERVO-GPIO] RPi.GPIO модуль доступен")
            logger.info("✅ RPi.GPIO модуль доступен")
        except ImportError:
            print("❌ [SERVO-GPIO] RPi.GPIO не установлен")
            print("   [SERVO-GPIO] Установите: pip install RPi.GPIO")
            print("   [SERVO-GPIO] Или запустите не на Raspberry Pi (программный режим)")
            logger.error("❌ RPi.GPIO не установлен")
            logger.error("   Установите: pip install RPi.GPIO")
            logger.error("   Или запустите не на Raspberry Pi (программный режим)")
            return False

        try:
            self._gpio = GPIO
            logger.info("⏳ Настройка GPIO режима (BCM)...")
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Setup pan servo
            if self.pan_pin:
                logger.info("⏳ Настройка Pan серво на GPIO %d...", self.pan_pin)
                GPIO.setup(self.pan_pin, GPIO.OUT)
                self.pan_pwm = GPIO.PWM(self.pan_pin, self.frequency)
                self.pan_pwm.start(0)
                logger.info("✅ Pan серво инициализирован")

            # Setup tilt servo
            if self.tilt_pin:
                logger.info("⏳ Настройка Tilt серво на GPIO %d...", self.tilt_pin)
                GPIO.setup(self.tilt_pin, GPIO.OUT)
                self.tilt_pwm = GPIO.PWM(self.tilt_pin, self.frequency)
                self.tilt_pwm.start(0)
                logger.info("✅ Tilt серво инициализирован")

            self._initialized = True
            print(f"✅ [SERVO-GPIO] GPIO сервоприводы успешно инициализированы")
            print(f"   [SERVO-GPIO] Pan: GPIO {self.pan_pin}, Tilt: GPIO {self.tilt_pin}, Частота: {self.frequency} Hz")
            logger.info("✅ GPIO сервоприводы успешно инициализированы")
            logger.info("   Pan: GPIO %d, Tilt: GPIO %d, Частота: %d Hz", 
                       self.pan_pin, self.tilt_pin, self.frequency)
            return True
        except RuntimeError as exc:
            print(f"❌ [SERVO-GPIO] Ошибка инициализации GPIO: {exc}")
            print(f"   [SERVO-GPIO] Возможные причины:")
            print(f"   1. GPIO уже используется другим процессом")
            print(f"   2. Недостаточно прав (нужны root или группа gpio)")
            print(f"   3. Неправильные номера пинов")
            logger.error("❌ Ошибка инициализации GPIO: %s", exc)
            logger.error("   Возможные причины:")
            logger.error("   1. GPIO уже используется другим процессом")
            logger.error("   2. Недостаточно прав (нужны root или группа gpio)")
            logger.error("   3. Неправильные номера пинов")
            return False
        except Exception as exc:
            print(f"❌ [SERVO-GPIO] Не удалось инициализировать GPIO сервоприводы: {exc}")
            print(f"   [SERVO-GPIO] Тип ошибки: {type(exc).__name__}")
            logger.error("❌ Не удалось инициализировать GPIO сервоприводы: %s", exc, exc_info=True)
            logger.error("   Тип ошибки: %s", type(exc).__name__)
            return False

    def set_angle(self, servo: str, angle: float) -> None:
        """Set servo angle. angle: 0-180 degrees."""
        print(f"🔧 [GPIO-SERVO] set_angle вызван: servo={servo}, angle={angle:.1f}°", flush=True)
        
        if not self._initialized:
            print(f"❌ [GPIO-SERVO] Контроллер не инициализирован!", flush=True)
            logger.warning(f"GPIO servo controller not initialized, cannot set {servo} angle")
            return

        # Clamp angle to valid range
        angle = max(0.0, min(180.0, angle))

        # Convert angle to duty cycle (0-180 degrees -> 2.5-12.5% duty cycle for standard servos)
        # Standard servos: 0° = 2.5%, 90° = 7.5%, 180° = 12.5%
        duty_cycle = 2.5 + (angle / 180.0) * 10.0
        print(f"   [GPIO-SERVO] Duty cycle: {duty_cycle:.2f}%", flush=True)

        try:
            if servo == "pan" and self.pan_pwm:
                print(f"⏳ [GPIO-SERVO] Установка Pan на GPIO {self.pan_pin}: duty_cycle={duty_cycle:.2f}%", flush=True)
                self.pan_pwm.ChangeDutyCycle(duty_cycle)
                print(f"✅ [GPIO-SERVO] Pan установлен на {angle:.1f}° (duty_cycle={duty_cycle:.2f}%)", flush=True)
            elif servo == "tilt" and self.tilt_pwm:
                print(f"⏳ [GPIO-SERVO] Установка Tilt на GPIO {self.tilt_pin}: duty_cycle={duty_cycle:.2f}%", flush=True)
                self.tilt_pwm.ChangeDutyCycle(duty_cycle)
                print(f"✅ [GPIO-SERVO] Tilt установлен на {angle:.1f}° (duty_cycle={duty_cycle:.2f}%)", flush=True)
            else:
                print(f"⚠️  [GPIO-SERVO] Неизвестный серво или PWM не инициализирован: servo={servo}, pan_pwm={self.pan_pwm is not None}, tilt_pwm={self.tilt_pwm is not None}", flush=True)
                logger.warning(f"Unknown servo '{servo}' or PWM not initialized")
        except Exception as exc:
            print(f"❌ [GPIO-SERVO] Ошибка установки {servo} серво: {exc}", flush=True)
            logger.error(f"Failed to set {servo} servo angle: {exc}", exc_info=True)

    def cleanup(self) -> None:
        """Cleanup GPIO resources."""
        if not self._initialized:
            return

        try:
            if self.pan_pwm:
                self.pan_pwm.stop()
            if self.tilt_pwm:
                self.tilt_pwm.stop()
            if self._gpio:
                self._gpio.cleanup()
            self._initialized = False
            logger.info("GPIO servos cleaned up")
        except Exception as exc:
            logger.error(f"Error cleaning up GPIO servos: {exc}")


class PCA9685ServoController(HardwareServoController):
    """Servo controller using PCA9685 I2C PWM controller.
    
    Requires: pip install adafruit-circuitpython-servokit
    Suitable for: Multiple servos via I2C (more stable, no GPIO conflicts)
    """

    def __init__(
        self,
        pan_channel: int = 0,
        tilt_channel: int = 1,
        address: int = 0x40,
        frequency: int = 50,
    ):
        """
        Args:
            pan_channel: PCA9685 channel for pan servo (0-15, default: 0)
            tilt_channel: PCA9685 channel for tilt servo (0-15, default: 1)
            address: I2C address of PCA9685 (default: 0x40)
            frequency: PWM frequency in Hz (default: 50 for standard servos)
        """
        super().__init__(pan_channel, tilt_channel)
        self.pan_channel = pan_channel
        self.tilt_channel = tilt_channel
        self.address = address
        self.frequency = frequency
        self._servo_kit = None

    def initialize(self) -> bool:
        """Initialize PCA9685."""
        print(f"🔌 [SERVO-PCA9685] Инициализация PCA9685 сервоприводов...")
        print(f"   [SERVO-PCA9685] Pan channel: {self.pan_channel}")
        print(f"   [SERVO-PCA9685] Tilt channel: {self.tilt_channel}")
        print(f"   [SERVO-PCA9685] I2C address: 0x{self.address:02x}")
        print(f"   [SERVO-PCA9685] Frequency: {self.frequency} Hz")
        logger.info("🔌 Инициализация PCA9685 сервоприводов...")
        logger.info("   Pan channel: %d", self.pan_channel)
        logger.info("   Tilt channel: %d", self.tilt_channel)
        logger.info("   I2C address: 0x%02x", self.address)
        logger.info("   Frequency: %d Hz", self.frequency)
        
        try:
            from adafruit_servokit import ServoKit
            print("✅ [SERVO-PCA9685] adafruit-circuitpython-servokit модуль доступен")
            logger.info("✅ adafruit-circuitpython-servokit модуль доступен")
        except ImportError:
            print("❌ [SERVO-PCA9685] adafruit-circuitpython-servokit не установлен")
            print("   [SERVO-PCA9685] Установите: pip install adafruit-circuitpython-servokit")
            logger.error("❌ adafruit-circuitpython-servokit не установлен")
            logger.error("   Установите: pip install adafruit-circuitpython-servokit")
            return False

        try:
            # Проверяем доступность I2C
            try:
                import board
                import busio
                logger.info("⏳ Проверка доступности I2C...")
                i2c = busio.I2C(board.SCL, board.SDA)
                logger.info("✅ I2C доступен")
            except Exception as i2c_exc:
                logger.error("❌ I2C недоступен: %s", i2c_exc)
                logger.error("   Проверьте:")
                logger.error("   1. I2C включен: sudo raspi-config → Interface Options → I2C → Enable")
                logger.error("   2. PCA9685 подключен к I2C шине")
                logger.error("   3. Правильный адрес I2C: 0x%02x", self.address)
                return False

            logger.info("⏳ Создание ServoKit (channels=16, address=0x%02x)...", self.address)
            self._servo_kit = ServoKit(channels=16, address=self.address, frequency=self.frequency)
            self._initialized = True
            print(f"✅ [SERVO-PCA9685] PCA9685 сервоприводы успешно инициализированы")
            print(f"   [SERVO-PCA9685] Pan: канал {self.pan_channel}, Tilt: канал {self.tilt_channel}, Адрес: 0x{self.address:02x}, Частота: {self.frequency} Hz")
            logger.info("✅ PCA9685 сервоприводы успешно инициализированы")
            logger.info("   Pan: канал %d, Tilt: канал %d, Адрес: 0x%02x, Частота: %d Hz",
                       self.pan_channel, self.tilt_channel, self.address, self.frequency)
            return True
        except ValueError as exc:
            print(f"❌ [SERVO-PCA9685] Ошибка инициализации PCA9685: {exc}")
            print(f"   [SERVO-PCA9685] Возможные причины:")
            print(f"   1. Неправильный I2C адрес (проверьте перемычки на PCA9685)")
            print(f"   2. PCA9685 не подключен к I2C шине")
            print(f"   3. Недостаточно питания для PCA9685")
            logger.error("❌ Ошибка инициализации PCA9685: %s", exc)
            logger.error("   Возможные причины:")
            logger.error("   1. Неправильный I2C адрес (проверьте перемычки на PCA9685)")
            logger.error("   2. PCA9685 не подключен к I2C шине")
            logger.error("   3. Недостаточно питания для PCA9685")
            return False
        except Exception as exc:
            print(f"❌ [SERVO-PCA9685] Не удалось инициализировать PCA9685 сервоприводы: {exc}")
            print(f"   [SERVO-PCA9685] Тип ошибки: {type(exc).__name__}")
            logger.error("❌ Не удалось инициализировать PCA9685 сервоприводы: %s", exc, exc_info=True)
            logger.error("   Тип ошибки: %s", type(exc).__name__)
            return False

    def set_angle(self, servo: str, angle: float) -> None:
        """Set servo angle. angle: 0-180 degrees."""
        if not self._initialized or not self._servo_kit:
            return

        # Clamp angle to valid range
        angle = max(0.0, min(180.0, angle))

        try:
            if servo == "pan":
                self._servo_kit.servo[self.pan_channel].angle = angle
            elif servo == "tilt":
                self._servo_kit.servo[self.tilt_channel].angle = angle
        except Exception as exc:
            logger.error(f"Failed to set {servo} servo angle: {exc}")

    def cleanup(self) -> None:
        """Cleanup PCA9685 resources."""
        if self._initialized:
            # PCA9685 doesn't need explicit cleanup
            self._initialized = False
            logger.info("PCA9685 servos cleaned up")


def create_servo_controller(
    hardware_type: str = "none",
    pan_pin: Optional[int] = None,
    tilt_pin: Optional[int] = None,
    pan_channel: Optional[int] = None,
    tilt_channel: Optional[int] = None,
    **kwargs,
) -> HardwareServoController:
    """
    Factory function to create appropriate servo controller.
    
    Args:
        hardware_type: "gpio", "pca9685", or "none" (software-only)
        pan_pin: GPIO pin for pan servo (for GPIO mode)
        tilt_pin: GPIO pin for tilt servo (for GPIO mode)
        pan_channel: PCA9685 channel for pan servo (for PCA9685 mode)
        tilt_channel: PCA9685 channel for tilt servo (for PCA9685 mode)
        **kwargs: Additional arguments (address, frequency, etc.)
    
    Returns:
        HardwareServoController instance
    """
    if hardware_type == "gpio":
        pan = pan_pin if pan_pin is not None else 18
        tilt = tilt_pin if tilt_pin is not None else 19
        freq = kwargs.get("frequency", 50)
        return GPIOServoController(pan_pin=pan, tilt_pin=tilt, frequency=freq)
    elif hardware_type == "pca9685":
        pan_ch = pan_channel if pan_channel is not None else 0
        tilt_ch = tilt_channel if tilt_channel is not None else 1
        address = kwargs.get("address", 0x40)
        freq = kwargs.get("frequency", 50)
        return PCA9685ServoController(
            pan_channel=pan_ch, tilt_channel=tilt_ch, address=address, frequency=freq
        )
    else:
        # Return None for software-only mode
        return None

