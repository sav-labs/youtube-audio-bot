import logging
import asyncio
from pathlib import Path
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from .youtube_downloader import YouTubeDownloader
from .database import DatabaseManager
from settings import settings


class UserStates(StatesGroup):
    """Состояния пользователя для FSM"""
    waiting_for_url = State()


class YouTubeAudioBot:
    """Основной класс Telegram бота для скачивания аудио из YouTube"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Инициализация компонентов
        self.session = AiohttpSession()
        self.bot = Bot(token=settings.BOT_TOKEN, session=self.session)
        self.dp = Dispatcher()
        self.downloader = YouTubeDownloader()
        self.db = DatabaseManager()
        
        # Регистрация обработчиков
        self._register_handlers()
        
        self.logger.info("YouTube Audio Bot инициализирован")
    
    def _register_handlers(self):
        """Регистрирует обработчики команд и сообщений"""
        self.dp.message.register(self._start_handler, Command("start"))
        self.dp.message.register(self._help_handler, Command("help"))
        self.dp.message.register(self._stats_handler, Command("stats"))
        self.dp.message.register(self._url_handler, UserStates.waiting_for_url)
        self.dp.message.register(self._default_handler)
    
    async def _start_handler(self, message: Message, state: FSMContext):
        """Обработчик команды /start"""
        await state.clear()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Скачать аудио", callback_data="download")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
        ])
        
        welcome_text = (
            "🎵 <b>YouTube Audio Bot</b>\n\n"
            "Привет! Я помогу тебе скачать аудио из YouTube видео.\n\n"
            "📋 <b>Что я умею:</b>\n"
            "• Скачивать аудио из YouTube видео\n"
            "• Конвертировать в MP3 формат\n"
            "• Отправлять готовый файл в Telegram\n\n"
            "Просто отправь мне ссылку на YouTube видео!"
        )
        
        await message.answer(
            welcome_text, 
            reply_markup=keyboard, 
            parse_mode=ParseMode.HTML
        )
        
        # Сохраняем пользователя в БД
        await self.db.add_user(message.from_user.id, message.from_user.username)
        
        self.logger.info(f"Пользователь {message.from_user.id} начал работу с ботом")
    
    async def _help_handler(self, message: Message):
        """Обработчик команды /help"""
        help_text = (
            "❓ <b>Справка по использованию</b>\n\n"
            "🔹 Отправьте мне ссылку на YouTube видео\n"
            "🔹 Бот автоматически скачает аудио\n"
            "🔹 Вы получите MP3 файл в личные сообщения\n\n"
            "📋 <b>Поддерживаемые форматы ссылок:</b>\n"
            "• https://www.youtube.com/watch?v=...\n"
            "• https://youtu.be/...\n"
            "• https://m.youtube.com/watch?v=...\n\n"
            "⚠️ <b>Ограничения:</b>\n"
            f"• Максимальный размер файла: {settings.MAX_FILE_SIZE} МБ\n"
            "• Только публичные видео\n"
            f"• Длительность до {settings.MAX_DURATION // 3600} час(ов)\n\n"
            "🤖 Команды:\n"
            "/start - Начать работу\n"
            "/help - Показать эту справку\n"
            "/stats - Статистика использования"
        )
        
        await message.answer(help_text, parse_mode=ParseMode.HTML)
    
    async def _stats_handler(self, message: Message):
        """Обработчик команды /stats"""
        stats = await self.db.get_user_stats(message.from_user.id)
        
        stats_text = (
            f"📊 <b>Ваша статистика</b>\n\n"
            f"🎵 Скачано файлов: {stats.get('downloads', 0)}\n"
            f"📅 Дата регистрации: {stats.get('registration_date', 'Неизвестно')}\n"
            f"⏰ Последняя активность: {stats.get('last_activity', 'Сейчас')}"
        )
        
        await message.answer(stats_text, parse_mode=ParseMode.HTML)
    
    async def _url_handler(self, message: Message, state: FSMContext):
        """Обработчик URL YouTube видео"""
        url = message.text.strip()
        
        if not self.downloader.is_valid_youtube_url(url):
            await message.answer(
                "❌ Некорректная ссылка YouTube!\n\n"
                "Пожалуйста, отправьте корректную ссылку на YouTube видео."
            )
            return
        
        # Отправляем сообщение о начале обработки
        processing_msg = await message.answer("⏳ Обрабатываю ваш запрос...")
        
        try:
            # Скачиваем аудио
            audio_file_path = await self.downloader.download_audio(url)
            
            if audio_file_path == "TOO_LONG":
                max_hours = settings.MAX_DURATION // 3600
                await processing_msg.edit_text(
                    "❌ Видео слишком длинное!\n\n"
                    f"⏱️ Максимальная длительность: {max_hours} час(а)\n"
                    "🎵 Попробуйте более короткое видео."
                )
                return
            
            if audio_file_path == "UNAVAILABLE":
                await processing_msg.edit_text(
                    "❌ Видео недоступно для скачивания!\n\n"
                    "🚫 Возможные причины:\n"
                    "• Видео заблокировано в вашем регионе\n"
                    "• Автор ограничил скачивание\n"
                    "• Видео было удалено\n\n"
                    "🔄 Попробуйте другое видео."
                )
                return
            
            if audio_file_path == "AGE_RESTRICTED":
                await processing_msg.edit_text(
                    "❌ Видео ограничено по возрасту!\n\n"
                    "🔞 Это видео имеет возрастные ограничения и не может быть скачано.\n\n"
                    "🔄 Попробуйте другое видео."
                )
                return
            
            if audio_file_path == "PRIVATE":
                await processing_msg.edit_text(
                    "❌ Видео приватное!\n\n"
                    "🔒 Это приватное видео недоступно для скачивания.\n\n"
                    "🔄 Попробуйте публичное видео."
                )
                return
            
            if not audio_file_path or not Path(audio_file_path).exists():
                await processing_msg.edit_text(
                    "❌ Не удалось скачать аудио.\n"
                    "Возможно, видео недоступно или превышен лимит размера."
                )
                return
            
            # Обновляем сообщение
            await processing_msg.edit_text("📤 Отправляю аудио файл...")
            
            # Отправляем аудио файл
            audio_file = Path(audio_file_path)
            with open(audio_file, 'rb') as audio:
                await message.answer_audio(
                    audio=audio,
                    caption=f"🎵 Аудио из YouTube видео\n📎 {url}",
                    parse_mode=ParseMode.HTML
                )
            
            # Удаляем временный файл
            audio_file.unlink(missing_ok=True)
            
            # Удаляем сообщение о процессе
            await processing_msg.delete()
            
            # Обновляем статистику
            await self.db.increment_user_downloads(message.from_user.id)
            
            self.logger.info(f"Успешно обработан запрос от пользователя {message.from_user.id}")
            
        except Exception as e:
            self.logger.error(f"Ошибка при обработке URL {url}: {e}")
            await processing_msg.edit_text(
                "❌ Произошла ошибка при обработке видео.\n"
                "Пожалуйста, попробуйте позже или с другой ссылкой."
            )
        
        finally:
            await state.clear()
    
    async def _default_handler(self, message: Message, state: FSMContext):
        """Обработчик для всех остальных сообщений"""
        text = message.text
        
        # Проверяем, является ли текст YouTube URL
        if self.downloader.is_valid_youtube_url(text):
            await state.set_state(UserStates.waiting_for_url)
            await self._url_handler(message, state)
        else:
            await message.answer(
                "🤔 Я не понимаю это сообщение.\n\n"
                "Отправьте мне ссылку на YouTube видео или используйте /help для получения справки."
            )
    
    async def start_polling(self):
        """Запускает бота в режиме polling"""
        try:
            self.logger.info("Запуск бота...")
            await self.dp.start_polling(self.bot)
        except Exception as e:
            self.logger.error(f"Ошибка при запуске бота: {e}")
            raise
        finally:
            await self.session.close()
    
    async def stop(self):
        """Корректно завершает работу бота"""
        self.logger.info("Остановка бота...")
        await self.session.close()
        await self.db.close() 