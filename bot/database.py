import logging
import asyncio
import aiosqlite
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from settings import settings


class DatabaseManager:
    """Класс для управления базой данных"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db_path = "data/bot.db"
        self._ensure_data_directory()
        
        # Создаем таблицы при инициализации
        asyncio.create_task(self._init_database())
    
    def _ensure_data_directory(self):
        """Создает директорию для базы данных если она не существует"""
        Path("data").mkdir(exist_ok=True)
    
    async def _init_database(self):
        """Инициализирует базу данных и создает таблицы"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Таблица пользователей
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        downloads_count INTEGER DEFAULT 0,
                        is_blocked BOOLEAN DEFAULT FALSE
                    )
                """)
                
                # Таблица загрузок
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS downloads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        youtube_url TEXT,
                        video_title TEXT,
                        file_size INTEGER,
                        download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        success BOOLEAN DEFAULT TRUE,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                """)
                
                # Индексы для оптимизации
                await db.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON downloads(user_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_download_date ON downloads(download_date)")
                
                await db.commit()
                self.logger.info("База данных инициализирована")
                
        except Exception as e:
            self.logger.error(f"Ошибка при инициализации базы данных: {e}")
    
    async def add_user(self, user_id: int, username: Optional[str] = None, 
                      first_name: Optional[str] = None, last_name: Optional[str] = None):
        """Добавляет нового пользователя или обновляет существующего"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Проверяем, существует ли пользователь
                cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                user_exists = await cursor.fetchone()
                
                if user_exists:
                    # Обновляем последнюю активность и данные пользователя
                    await db.execute("""
                        UPDATE users 
                        SET username = ?, first_name = ?, last_name = ?, last_activity = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    """, (username, first_name, last_name, user_id))
                else:
                    # Добавляем нового пользователя
                    await db.execute("""
                        INSERT INTO users (user_id, username, first_name, last_name)
                        VALUES (?, ?, ?, ?)
                    """, (user_id, username, first_name, last_name))
                
                await db.commit()
                self.logger.info(f"Пользователь {user_id} добавлен/обновлен в базе данных")
                
        except Exception as e:
            self.logger.error(f"Ошибка при добавлении пользователя {user_id}: {e}")
    
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Получает статистику пользователя"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Получаем основную информацию о пользователе
                cursor = await db.execute("""
                    SELECT registration_date, last_activity, downloads_count 
                    FROM users WHERE user_id = ?
                """, (user_id,))
                
                user_data = await cursor.fetchone()
                
                if not user_data:
                    return {
                        'downloads': 0,
                        'registration_date': 'Неизвестно',
                        'last_activity': 'Сейчас'
                    }
                
                reg_date, last_activity, downloads_count = user_data
                
                return {
                    'downloads': downloads_count or 0,
                    'registration_date': reg_date,
                    'last_activity': last_activity
                }
                
        except Exception as e:
            self.logger.error(f"Ошибка при получении статистики пользователя {user_id}: {e}")
            return {'downloads': 0, 'registration_date': 'Неизвестно', 'last_activity': 'Сейчас'}
    
    async def increment_user_downloads(self, user_id: int):
        """Увеличивает счетчик загрузок пользователя"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE users 
                    SET downloads_count = downloads_count + 1, last_activity = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (user_id,))
                
                await db.commit()
                self.logger.debug(f"Увеличен счетчик загрузок для пользователя {user_id}")
                
        except Exception as e:
            self.logger.error(f"Ошибка при увеличении счетчика загрузок для пользователя {user_id}: {e}")
    
    async def log_download(self, user_id: int, youtube_url: str, video_title: str, 
                          file_size: int, success: bool = True):
        """Логирует информацию о загрузке"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO downloads (user_id, youtube_url, video_title, file_size, success)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, youtube_url, video_title, file_size, success))
                
                await db.commit()
                self.logger.info(f"Загрузка записана в базу данных: {video_title}")
                
        except Exception as e:
            self.logger.error(f"Ошибка при записи загрузки в базу данных: {e}")
    
    async def get_download_history(self, user_id: int, limit: int = 10) -> list:
        """Получает историю загрузок пользователя"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT youtube_url, video_title, file_size, download_date, success
                    FROM downloads 
                    WHERE user_id = ? 
                    ORDER BY download_date DESC 
                    LIMIT ?
                """, (user_id, limit))
                
                downloads = await cursor.fetchall()
                return [
                    {
                        'url': row[0],
                        'title': row[1],
                        'size': row[2],
                        'date': row[3],
                        'success': row[4]
                    }
                    for row in downloads
                ]
                
        except Exception as e:
            self.logger.error(f"Ошибка при получении истории загрузок пользователя {user_id}: {e}")
            return []
    
    async def get_admin_stats(self) -> Dict[str, Any]:
        """Получает общую статистику для администраторов"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Общее количество пользователей
                cursor = await db.execute("SELECT COUNT(*) FROM users")
                total_users = (await cursor.fetchone())[0]
                
                # Общее количество загрузок
                cursor = await db.execute("SELECT COUNT(*) FROM downloads WHERE success = TRUE")
                total_downloads = (await cursor.fetchone())[0]
                
                # Активные пользователи (за последние 7 дней)
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM users 
                    WHERE last_activity >= datetime('now', '-7 days')
                """)
                active_users = (await cursor.fetchone())[0]
                
                return {
                    'total_users': total_users,
                    'total_downloads': total_downloads,
                    'active_users': active_users
                }
                
        except Exception as e:
            self.logger.error(f"Ошибка при получении статистики для администраторов: {e}")
            return {'total_users': 0, 'total_downloads': 0, 'active_users': 0}
    
    async def close(self):
        """Закрывает соединение с базой данных"""
        # В случае aiosqlite соединения закрываются автоматически
        self.logger.info("Соединение с базой данных закрыто") 