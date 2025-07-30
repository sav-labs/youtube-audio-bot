import asyncio
import logging
import signal
import sys
from dotenv import load_dotenv

from bot.logger import setup_logging
from bot.youtube_audio_bot import YouTubeAudioBot


class BotApplication:
    """Основное приложение бота"""
    
    def __init__(self):
        self.bot = None
        self.logger = None
        self._shutdown_event = asyncio.Event()
    
    async def startup(self):
        """Инициализация и запуск бота"""
        try:
            # Загружаем переменные окружения
            load_dotenv()
            
            # Настраиваем логгирование
            setup_logging()
            self.logger = logging.getLogger(self.__class__.__name__)
            
            self.logger.info("=" * 50)
            self.logger.info("Запуск YouTube Audio Bot")
            self.logger.info("=" * 50)
            
            # Создаем и запускаем бота
            self.bot = YouTubeAudioBot()
            
            # Настраиваем обработчики сигналов для корректного завершения
            self._setup_signal_handlers()
            
            self.logger.info("Бот готов к работе!")
            
            # Запускаем polling
            await self.bot.start_polling()
            
        except KeyboardInterrupt:
            self.logger.info("Получен сигнал прерывания")
        except Exception as e:
            self.logger.error(f"Критическая ошибка при запуске бота: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Корректное завершение работы бота"""
        if self.logger:
            self.logger.info("Завершение работы бота...")
        
        if self.bot:
            await self.bot.stop()
        
        if self.logger:
            self.logger.info("Бот остановлен")
    
    def _setup_signal_handlers(self):
        """Настраивает обработчики сигналов для корректного завершения"""
        if sys.platform != 'win32':
            # Unix-системы
            loop = asyncio.get_event_loop()
            
            def signal_handler():
                self.logger.info("Получен сигнал завершения")
                self._shutdown_event.set()
            
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, signal_handler)


async def main():
    """Основная функция запуска"""
    app = BotApplication()
    await app.startup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма завершена пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1) 