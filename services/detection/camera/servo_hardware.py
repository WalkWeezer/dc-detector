"""Hardware implementations for servo control."""
from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class HardwareServoController:
    """Base class for hardware servo controllers."""

    def __init__(self, pan_pin: Optional[int] = None, tilt_pin: Optional[int] = None):
        self.pan_pin = pan_pin
        self.tilt_pin = tilt_pin
        self._initialized = False
        # Добавляем тайминги
        self._last_pan_angle = None
        self._last_tilt_angle = None
        self._min_angle_change = 0.5  # Минимальное изменение угла для отправки команды

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
    
    def should_update_angle(self, servo: str, new_angle: float) -> bool:
        """Проверяет, нужно ли отправлять новую команду на серво."""
        last_angle = self._last_pan_angle if servo == "pan" else self._last_tilt_angle
        if last_angle is None:
            return True
        if abs(new_angle - last_angle) < self._min_angle_change:
            return False
        return True
    
    def _update_last_angle(self, servo: str, angle: float) -> None:
        """Обновляет последний известный угол."""
        if servo == "pan":
            self._last_pan_angle = angle
        elif servo == "tilt":
            self._last_tilt_angle = angle


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
        # Защита от слишком частых команд
        self._last_pan_command = 0.0
        self._last_tilt_command = 0.0
        self._min_command_interval = 0.1  # 100ms между командами

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
                # Запускаем с нейтральной позицией (7.5% = 90 градусов) вместо 0
                self.pan_pwm.start(7.5)
                # Сразу даем время стабилизироваться
                time.sleep(0.1)
                logger.info("✅ Pan серво инициализирован (начальная позиция: 90°)")

            # Setup tilt servo
            if self.tilt_pin:
                logger.info("⏳ Настройка Tilt серво на GPIO %d...", self.tilt_pin)
                GPIO.setup(self.tilt_pin, GPIO.OUT)
                self.tilt_pwm = GPIO.PWM(self.tilt_pin, self.frequency)
                # Запускаем с нейтральной позицией (7.5% = 90 градусов) вместо 0
                self.tilt_pwm.start(7.5)
                # Сразу даем время стабилизироваться
                time.sleep(0.1)
                logger.info("✅ Tilt серво инициализирован (начальная позиция: 90°)")

            self._initialized = True
            self._last_pan_angle = 90.0
            self._last_tilt_angle = 90.0
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
        current_time = time.time()
        
        # Проверяем интервал между командами
        if servo == "pan":
            if current_time - self._last_pan_command < self._min_command_interval:
                print(f"   [GPIO-SERVO] Пропуск Pan команды: слишком часто (интервал {self._min_command_interval}с)", flush=True)
                return
            self._last_pan_command = current_time
        elif servo == "tilt":
            if current_time - self._last_tilt_command < self._min_command_interval:
                print(f"   [GPIO-SERVO] Пропуск Tilt команды: слишком часто (интервал {self._min_command_interval}с)", flush=True)
                return
            self._last_tilt_command = current_time
        
        # Проверяем, нужно ли обновлять угол
        if not self.should_update_angle(servo, angle):
            print(f"   [GPIO-SERVO] {servo}: пропуск (изменение меньше {self._min_angle_change}°)", flush=True)
            return
        
        last_angle = self._last_pan_angle if servo == "pan" else self._last_tilt_angle
        print(f"🔧 [GPIO-SERVO] set_angle: servo={servo}, angle={angle:.1f}°, last={last_angle}", flush=True)
        
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
                logger.info("⏳ [GPIO-SERVO] Установка Pan на GPIO %d: угол=%.1f°, duty_cycle=%.2f%%", 
                           self.pan_pin, angle, duty_cycle)
                
                # Устанавливаем новый duty cycle напрямую
                # PWM должен работать постоянно для удержания позиции сервопривода
                print(f"   [GPIO-SERVO] Отправка команды на GPIO {self.pan_pin}: ChangeDutyCycle({duty_cycle:.2f}%)", flush=True)
                logger.info("   [GPIO-SERVO] Отправка команды на GPIO %d: ChangeDutyCycle(%.2f%%)", 
                           self.pan_pin, duty_cycle)
                self.pan_pwm.ChangeDutyCycle(duty_cycle)
                print(f"   [GPIO-SERVO] ✅ Команда отправлена на GPIO {self.pan_pin}", flush=True)
                
                # Обновляем последний угол
                self._update_last_angle(servo, angle)
                
                print(f"✅ [GPIO-SERVO] Pan установлен на {angle:.1f}° (PWM активен, duty_cycle={duty_cycle:.2f}%)", flush=True)
                logger.info("✅ [GPIO-SERVO] Pan установлен на %.1f° на GPIO %d (PWM активен, duty_cycle=%.2f%%)", 
                           angle, self.pan_pin, duty_cycle)
                
            elif servo == "tilt" and self.tilt_pwm:
                print(f"⏳ [GPIO-SERVO] Установка Tilt на GPIO {self.tilt_pin}: duty_cycle={duty_cycle:.2f}%", flush=True)
                logger.info("⏳ [GPIO-SERVO] Установка Tilt на GPIO %d: угол=%.1f°, duty_cycle=%.2f%%", 
                           self.tilt_pin, angle, duty_cycle)
                
                # Устанавливаем новый duty cycle напрямую
                # PWM должен работать постоянно для удержания позиции сервопривода
                print(f"   [GPIO-SERVO] Отправка команды на GPIO {self.tilt_pin}: ChangeDutyCycle({duty_cycle:.2f}%)", flush=True)
                logger.info("   [GPIO-SERVO] Отправка команды на GPIO %d: ChangeDutyCycle(%.2f%%)", 
                           self.tilt_pin, duty_cycle)
                self.tilt_pwm.ChangeDutyCycle(duty_cycle)
                print(f"   [GPIO-SERVO] ✅ Команда отправлена на GPIO {self.tilt_pin}", flush=True)
                
                # Обновляем последний угол
                self._update_last_angle(servo, angle)
                
                print(f"✅ [GPIO-SERVO] Tilt установлен на {angle:.1f}° (PWM активен, duty_cycle={duty_cycle:.2f}%)", flush=True)
                logger.info("✅ [GPIO-SERVO] Tilt установлен на %.1f° на GPIO %d (PWM активен, duty_cycle=%.2f%%)", 
                           angle, self.tilt_pin, duty_cycle)
            else:
                print(f"⚠️  [GPIO-SERVO] Неизвестный серво или PWM не инициализирован: servo={servo}", flush=True)
                logger.warning(f"Unknown servo '{servo}' or PWM not initialized")
        except Exception as exc:
            print(f"❌ [GPIO-SERVO] Ошибка установки {servo} серво: {exc}", flush=True)
            logger.error(f"Failed to set {servo} servo angle: {exc}", exc_info=True)

    def cleanup(self) -> None:
        """Cleanup GPIO resources."""
        if not self._initialized:
            return

        try:
            print(f"🧹 [GPIO-SERVO] Очистка GPIO ресурсов...", flush=True)
            
            # Сначала останавливаем PWM
            if self.pan_pwm:
                print(f"   [GPIO-SERVO] Остановка Pan PWM...", flush=True)
                self.pan_pwm.ChangeDutyCycle(0)
                time.sleep(0.01)
                self.pan_pwm.stop()
                
            if self.tilt_pwm:
                print(f"   [GPIO-SERVO] Остановка Tilt PWM...", flush=True)
                self.tilt_pwm.ChangeDutyCycle(0)
                time.sleep(0.01)
                self.tilt_pwm.stop()
                
            # Затем очищаем GPIO
            if self._gpio:
                print(f"   [GPIO-SERVO] Очистка GPIO...", flush=True)
                self._gpio.cleanup()
                
            self._initialized = False
            print(f"✅ [GPIO-SERVO] GPIO ресурсы очищены", flush=True)
            logger.info("GPIO servos cleaned up")
        except Exception as exc:
            print(f"❌ [GPIO-SERVO] Ошибка очистки GPIO: {exc}", flush=True)
            logger.error(f"Error cleaning up GPIO servos: {exc}")


def create_servo_controller(
    hardware_type: str = "none",
    pan_pin: Optional[int] = None,
    tilt_pin: Optional[int] = None,
    **kwargs,
) -> HardwareServoController:
    """
    Factory function to create appropriate servo controller.
    
    Args:
        hardware_type: "gpio", or "none" (software-only)
        pan_pin: GPIO pin for pan servo (for GPIO mode)
        tilt_pin: GPIO pin for tilt servo (for GPIO mode)
        **kwargs: Additional arguments (frequency, etc.)
    
    Returns:
        HardwareServoController instance
    """
    if hardware_type == "gpio":
        pan = pan_pin if pan_pin is not None else 18
        tilt = tilt_pin if tilt_pin is not None else 19
        freq = kwargs.get("frequency", 50)
        return GPIOServoController(pan_pin=pan, tilt_pin=tilt, frequency=freq)
    else:
        # Return None for software-only mode
        return None