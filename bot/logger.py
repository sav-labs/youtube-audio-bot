import logging
import logging.handlers
from pathlib import Path
from settings import settings


def setup_logging():
    """Настраивает систему логгирования"""
    
    # Создаем директорию для логов
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.get_log_level())
    
    # Очищаем существующие обработчики
    root_logger.handlers.clear()
    
    # Форматтер для логов
    formatter = logging.Formatter(
        fmt=settings.LOG_FORMAT,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Обработчик для консоли
    console_handler = logging.StreamHandler()
    console_handler.setLevel(settings.get_log_level())
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Обработчик для файла (с ротацией)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "bot.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Отдельный файл для ошибок
    error_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "errors.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # Настройка логгеров внешних библиотек
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("yt_dlp").setLevel(logging.WARNING)
    
    logging.info("Система логгирования настроена")


def get_logger(name: str) -> logging.Logger:
    """Возвращает настроенный логгер для указанного модуля"""
    return logging.getLogger(name) 