"""MavLink GPS reader for getting drone GPS coordinates."""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from pymavlink import mavutil
    MAVLINK_AVAILABLE = True
except ImportError:
    MAVLINK_AVAILABLE = False
    mavutil = None  # type: ignore[assignment, misc]


class MavLinkGPSReader:
    """Читает GPS координаты через MavLink протокол."""

    def __init__(self, port: str, baudrate: int = 57600):
        """
        Инициализирует MavLink GPS reader.

        Args:
            port: Порт для подключения:
                  - Аппаратный UART на GPIO (Raspberry Pi): '/dev/ttyAMA0' или '/dev/serial0' (GPIO 14/15)
                  - Software UART на GPIO: '/dev/ttyAMA2' или '/dev/ttyAMA3' (настроенные через config.txt)
                  - USB последовательный: '/dev/ttyUSB0' или 'COM3' (Windows)
                  - UDP: 'udp:127.0.0.1:14550'
                  - TCP: 'tcp:192.168.1.100:5760'
            baudrate: Скорость для последовательного порта (по умолчанию 57600)
        """
        self.port = port
        self.baudrate = baudrate
        self.connection: Optional[object] = None
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.reader_thread: Optional[threading.Thread] = None
        
        # Текущие GPS координаты
        self.latitude: Optional[float] = None
        self.longitude: Optional[float] = None
        self.altitude: Optional[float] = None
        self.gps_fix_type: int = 0  # 0 = нет фикса, 2 = 2D фикс, 3 = 3D фикс
        self.last_update_time: float = 0.0
        
        self._running = False

    def start(self) -> bool:
        """Запускает подключение к MavLink и поток чтения GPS."""
        if not MAVLINK_AVAILABLE:
            logger.error("❌ pymavlink не установлен. Установите: pip install pymavlink")
            return False

        if self._running:
            logger.warning("MavLink GPS reader уже запущен")
            return True

        logger.info("🔌 Попытка подключения к MavLink...")
        logger.info("   Порт: %s", self.port)
        logger.info("   Скорость: %d", self.baudrate)

        try:
            # Проверяем доступность порта для последовательных портов
            if self.port.startswith('/dev/') or self.port.startswith('COM'):
                import os
                if not os.path.exists(self.port):
                    logger.error("❌ Последовательный порт не найден: %s", self.port)
                    logger.error("   Проверьте, что порт существует и доступен")
                    logger.error("   Команда для проверки: ls -l %s", self.port)
                    return False
                
                # Проверяем права доступа
                if not os.access(self.port, os.R_OK | os.W_OK):
                    logger.error("❌ Нет прав доступа к порту: %s", self.port)
                    logger.error("   Решение: sudo usermod -a -G dialout $USER")
                    logger.error("   Затем перелогиньтесь")
                    return False

            # Определяем тип подключения
            if self.port.startswith('udp:') or self.port.startswith('tcp:'):
                # UDP или TCP подключение
                connection_string = self.port
            elif self.port.startswith('/dev/') or self.port.startswith('COM'):
                # Последовательный порт
                connection_string = f"{self.port}:{self.baudrate}"
            else:
                # Пробуем как UDP
                connection_string = f"udp:{self.port}"

            logger.info("📡 Строка подключения: %s", connection_string)
            logger.info("⏳ Создание подключения...")
            
            self.connection = mavutil.mavlink_connection(connection_string)
            
            logger.info("⏳ Ожидание heartbeat от автопилота (таймаут 10 сек)...")
            self.connection.wait_heartbeat(timeout=10)
            
            logger.info("✅ MavLink подключение установлено!")
            logger.info("   System ID: %u", self.connection.target_system)
            logger.info("   Component ID: %u", self.connection.target_component)

            self._running = True
            self.stop_event.clear()
            self.reader_thread = threading.Thread(target=self._read_loop, name="mavlink-gps-reader", daemon=True)
            self.reader_thread.start()
            logger.info("✅ MavLink GPS reader запущен и ожидает GPS данные...")
            return True

        except TimeoutError:
            logger.error("❌ Таймаут ожидания heartbeat от автопилота")
            logger.error("   Проверьте:")
            logger.error("   1. Автопилот включен и подключен")
            logger.error("   2. Правильный порт: %s", self.port)
            logger.error("   3. Правильная скорость: %d", self.baudrate)
            logger.error("   4. Кабель подключен правильно")
            self.connection = None
            self._running = False
            return False
        except FileNotFoundError as exc:
            logger.error("❌ Порт не найден: %s", exc)
            logger.error("   Проверьте, что порт существует: ls -l %s", self.port)
            self.connection = None
            self._running = False
            return False
        except PermissionError as exc:
            logger.error("❌ Нет прав доступа к порту: %s", exc)
            logger.error("   Решение: sudo usermod -a -G dialout $USER")
            logger.error("   Затем перелогиньтесь")
            self.connection = None
            self._running = False
            return False
        except Exception as exc:
            logger.error("❌ Не удалось подключиться к MavLink: %s", exc, exc_info=True)
            logger.error("   Тип ошибки: %s", type(exc).__name__)
            self.connection = None
            self._running = False
            return False

    def stop(self) -> None:
        """Останавливает подключение и поток чтения."""
        if not self._running:
            return

        self._running = False
        self.stop_event.set()

        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=2)

        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None

        logger.info("MavLink GPS reader остановлен")

    def get_gps(self) -> Optional[Tuple[float, float, Optional[float]]]:
        """
        Возвращает текущие GPS координаты.

        Returns:
            Tuple (latitude, longitude, altitude) или None если GPS недоступен
        """
        with self.lock:
            if self.latitude is not None and self.longitude is not None:
                return (self.latitude, self.longitude, self.altitude)
            return None

    def get_gps_with_status(self) -> dict:
        """
        Возвращает GPS координаты со статусом.

        Returns:
            Dict с полями: latitude, longitude, altitude, fix_type, last_update
        """
        with self.lock:
            return {
                "latitude": self.latitude,
                "longitude": self.longitude,
                "altitude": self.altitude,
                "fix_type": self.gps_fix_type,
                "last_update": self.last_update_time,
                "available": self.latitude is not None and self.longitude is not None
            }

    def get_connection_status(self) -> dict:
        """
        Возвращает детальный статус подключения MavLink.
        
        Returns:
            Dict с детальной информацией о состоянии подключения
        """
        with self.lock:
            status = {
                "available": MAVLINK_AVAILABLE,
                "configured": self.port is not None,
                "port": self.port,
                "baudrate": self.baudrate,
                "running": self._running,
                "connected": self.connection is not None,
                "has_gps": self.latitude is not None and self.longitude is not None,
                "gps_fix_type": self.gps_fix_type,
                "last_update": self.last_update_time,
                "thread_alive": self.reader_thread.is_alive() if self.reader_thread else False,
            }
            
            # Дополнительная информация об ошибках
            if not MAVLINK_AVAILABLE:
                status["error"] = "pymavlink не установлен. Установите: pip install pymavlink"
            elif not self.port:
                status["error"] = "MAVLINK_PORT не настроен в переменных окружения"
            elif not self._running:
                status["error"] = "MavLink reader не запущен"
            elif not self.connection:
                status["error"] = "Подключение не установлено"
            elif self.reader_thread and not self.reader_thread.is_alive():
                status["error"] = "Поток чтения не запущен"
            
            return status

    def _read_loop(self) -> None:
        """Основной цикл чтения сообщений MavLink."""
        if not self.connection:
            return

        while self._running and not self.stop_event.is_set():
            try:
                # Читаем сообщение с таймаутом
                msg = self.connection.recv_match(type=['GPS_RAW_INT', 'GLOBAL_POSITION_INT'], timeout=1.0)
                
                if msg is None:
                    continue

                if msg.get_type() == 'GPS_RAW_INT':
                    # GPS_RAW_INT сообщение
                    lat = msg.lat / 1e7  # Конвертируем из 1e7 градусов
                    lon = msg.lon / 1e7
                    alt = msg.alt / 1000.0  # Конвертируем из мм в метры
                    fix_type = msg.fix_type

                    with self.lock:
                        if fix_type >= 2:  # 2D или 3D фикс
                            self.latitude = lat
                            self.longitude = lon
                            self.altitude = alt
                            self.gps_fix_type = fix_type
                            self.last_update_time = time.time()

                elif msg.get_type() == 'GLOBAL_POSITION_INT':
                    # GLOBAL_POSITION_INT сообщение (более точное)
                    lat = msg.lat / 1e7
                    lon = msg.lon / 1e7
                    alt = msg.alt / 1000.0  # Высота относительно уровня моря в метрах
                    relative_alt = msg.relative_alt / 1000.0  # Высота относительно взлета

                    with self.lock:
                        self.latitude = lat
                        self.longitude = lon
                        self.altitude = relative_alt if relative_alt != 0 else alt
                        self.gps_fix_type = 3  # Предполагаем 3D фикс для GLOBAL_POSITION_INT
                        self.last_update_time = time.time()

            except Exception as exc:
                logger.debug("Ошибка чтения MavLink сообщения: %s", exc)
                time.sleep(0.1)

        logger.info("MavLink GPS reader цикл завершен")

