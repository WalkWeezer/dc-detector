#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Скрипт для конвертации YOLO моделей в оптимизированные форматы"""

import argparse
import logging
import sys
from pathlib import Path

# Добавляем корень проекта в путь
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.detection.models.manager import ModelManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def convert_model_to_onnx(model_path: str, output_path: str = None, imgsz: int = 640) -> bool:
    """Конвертирует модель в ONNX формат"""
    try:
        from ultralytics import YOLO
        
        model_path_obj = Path(model_path)
        if not model_path_obj.exists():
            logger.error(f"Модель не найдена: {model_path}")
            return False
        
        logger.info(f"Загрузка модели: {model_path}")
        model = YOLO(str(model_path_obj))
        
        if output_path is None:
            output_path = str(model_path_obj.with_suffix('.onnx'))
        else:
            output_path = str(Path(output_path))
        
        logger.info(f"Конвертация в ONNX: {output_path} (размер: {imgsz})")
        
        # Экспорт в ONNX с оптимизацией для CPU
        model.export(
            format='onnx',
            imgsz=imgsz,
            optimize=True,  # Оптимизация для CPU
            half=False,  # FP32 для совместимости
        )
        
        logger.info(f"✅ Модель успешно конвертирована: {output_path}")
        return True
        
    except ImportError:
        logger.error("ultralytics не установлен. Установите: pip install ultralytics")
        return False
    except Exception as exc:
        logger.error(f"Ошибка конвертации: {exc}", exc_info=True)
        return False


def main():
    parser = argparse.ArgumentParser(description='Конвертация YOLO моделей в оптимизированные форматы')
    parser.add_argument('model_path', type=str, help='Путь к модели (.pt)')
    parser.add_argument('--output', '-o', type=str, default=None, help='Путь для сохранения конвертированной модели')
    parser.add_argument('--format', '-f', type=str, default='onnx', choices=['onnx'], help='Формат конвертации')
    parser.add_argument('--imgsz', type=int, default=640, help='Размер входного изображения (по умолчанию 640)')
    
    args = parser.parse_args()
    
    if args.format == 'onnx':
        success = convert_model_to_onnx(args.model_path, args.output, args.imgsz)
        sys.exit(0 if success else 1)
    else:
        logger.error(f"Неподдерживаемый формат: {args.format}")
        sys.exit(1)


if __name__ == '__main__':
    main()

