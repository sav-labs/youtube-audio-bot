import os
import logging
from typing import List
from pathlib import Path

class Settings:
    """Класс для управления настройками приложения"""
    
    def __init__(self):
        # Основные настройки бота
        self.BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
        self.BOT_ADMINS: List[int] = self._parse_admins(os.getenv("BOT_ADMINS", ""))
        
        # Настройки логгирования
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
        self.LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        
        # Настройки загрузки
        self.DOWNLOAD_DIR: Path = Path("downloads")
        self.MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "50"))  # MB
        self.TEMP_DIR: Path = Path("temp")
        
        # Настройки базы данных
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///bot.db")
        
        # Создаем необходимые директории
        self._create_directories()
        
        # Валидация настроек
        self._validate_settings()
    
    def _parse_admins(self, admins_str: str) -> List[int]:
        """Парсит строку администраторов в список ID"""
        if not admins_str:
            return []
        
        try:
            return [int(admin_id.strip()) for admin_id in admins_str.split(",") if admin_id.strip()]
        except ValueError:
            logging.warning("Некорректный формат BOT_ADMINS. Используется пустой список.")
            return []
    
    def _create_directories(self):
        """Создает необходимые директории"""
        self.DOWNLOAD_DIR.mkdir(exist_ok=True)
        self.TEMP_DIR.mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
    
    def _validate_settings(self):
        """Валидирует критически важные настройки"""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не может быть пустым!")
        
        if self.LOG_LEVEL not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            self.LOG_LEVEL = "INFO"
    
    def get_log_level(self) -> int:
        """Возвращает числовое значение уровня логгирования"""
        return getattr(logging, self.LOG_LEVEL)

# Глобальный экземпляр настроек
settings = Settings() 