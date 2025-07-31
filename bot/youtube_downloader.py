import re
import logging
import asyncio
from pathlib import Path
from typing import Optional
import uuid
import os
from pytubefix import YouTube
from pydub import AudioSegment
from settings import settings

# Настройки для обхода блокировок
import ssl
ssl._create_default_https_context = ssl._create_unverified_context


class YouTubeDownloader:
    """Класс для скачивания аудио из YouTube видео"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def is_valid_youtube_url(self, url: str) -> bool:
        """Проверяет, является ли URL корректной ссылкой на YouTube"""
        youtube_regex = re.compile(
            r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
            r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
        )
        
        return bool(youtube_regex.match(url))
    
    def _clean_url(self, url: str) -> str:
        """Очищает URL от лишних параметров"""
        # Убираем все параметры кроме основного video ID
        import re
        
        # Различные форматы YouTube URL
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                return f"https://www.youtube.com/watch?v={video_id}"
        
        # Если паттерн не найден, возвращаем исходный URL
        return url
    
    async def get_video_info(self, url: str) -> Optional[dict]:
        """Получает информацию о видео без скачивания"""
        try:
            url = self._clean_url(url)
            loop = asyncio.get_event_loop()
            
            def extract_info():
                # Добавляем дополнительные параметры для обхода ограничений
                yt = YouTube(
                    url,
                    use_oauth=False,
                    allow_oauth_cache=False
                )
                
                # Проверяем доступность видео
                if not yt.title:
                    raise Exception("Видео недоступно или не найдено")
                
                return {
                    'title': yt.title,
                    'duration': yt.length,
                    'author': yt.author,
                    'video_id': yt.video_id,
                    'views': yt.views if hasattr(yt, 'views') else 0,
                    'description': yt.description[:500] if yt.description else "",
                    'age_restricted': yt.age_restricted if hasattr(yt, 'age_restricted') else False
                }
            
            info = await loop.run_in_executor(None, extract_info)
            return info
            
        except Exception as e:
            error_msg = str(e).lower()
            if "unavailable" in error_msg:
                self.logger.error(f"Видео недоступно для скачивания {url}: {e}")
                return "UNAVAILABLE"
            elif "age" in error_msg or "restricted" in error_msg:
                self.logger.error(f"Видео ограничено по возрасту {url}: {e}")
                return "AGE_RESTRICTED"
            elif "private" in error_msg:
                self.logger.error(f"Видео приватное {url}: {e}")
                return "PRIVATE"
            else:
                self.logger.error(f"Ошибка при получении информации о видео {url}: {e}")
                return None
    
    async def download_audio(self, url: str) -> Optional[str]:
        """Скачивает аудио из YouTube видео и возвращает путь к файлу"""
        try:
            url = self._clean_url(url)
            
            # Получаем информацию о видео
            info = await self.get_video_info(url)
            if not info:
                self.logger.error(f"Не удалось получить информацию о видео: {url}")
                return None
            
            # Обрабатываем специальные статусы ошибок
            if info == "UNAVAILABLE":
                return "UNAVAILABLE"
            elif info == "AGE_RESTRICTED":
                return "AGE_RESTRICTED"
            elif info == "PRIVATE":
                return "PRIVATE"
            
            # Проверяем длительность видео
            duration = info.get('duration', 0)
            if duration > settings.MAX_DURATION:
                hours = settings.MAX_DURATION // 3600
                self.logger.warning(f"Видео слишком длинное ({duration} сек, лимит: {settings.MAX_DURATION} сек): {url}")
                return "TOO_LONG"
            
            # Скачиваем аудио
            loop = asyncio.get_event_loop()
            
            def download():
                # Используем те же параметры что и в get_video_info
                yt = YouTube(
                    url,
                    use_oauth=False,
                    allow_oauth_cache=False
                )
                
                # Получаем аудио потоки (пробуем разные варианты)
                audio_streams = [
                    yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc(),
                    yt.streams.filter(only_audio=True).order_by('abr').desc(),
                    yt.streams.filter(adaptive=True, only_audio=True).order_by('abr').desc(),
                    yt.streams.filter(file_extension='mp4').order_by('abr').desc()
                ]
                
                audio_stream = None
                for streams in audio_streams:
                    if streams:
                        audio_stream = streams.first()
                        if audio_stream:
                            break
                
                if not audio_stream:
                    self.logger.error("Не удалось найти подходящий аудио поток")
                    return None
                
                self.logger.info(f"Найден аудио поток: {audio_stream.mime_type}, качество: {getattr(audio_stream, 'abr', 'unknown')}")
                
                # Генерируем уникальное имя файла
                unique_id = str(uuid.uuid4())[:8]
                safe_title = re.sub(r'[^\w\s-]', '', info['title']).strip()[:50]
                temp_filename = f"{safe_title}_{unique_id}"
                
                # Определяем расширение файла
                file_extension = audio_stream.mime_type.split('/')[-1] if audio_stream.mime_type else 'mp4'
                
                # Скачиваем во временную директорию
                temp_path = settings.TEMP_DIR / f"{temp_filename}.{file_extension}"
                
                self.logger.info(f"Начинаем скачивание: {temp_filename}.{file_extension}")
                audio_stream.download(output_path=str(settings.TEMP_DIR), filename=f"{temp_filename}.{file_extension}")
                
                return str(temp_path)
            
            temp_file_path = await loop.run_in_executor(None, download)
            
            if not temp_file_path or not Path(temp_file_path).exists():
                self.logger.error("Не удалось скачать аудио файл")
                return None
            
            # Конвертируем в MP3
            mp3_file_path = await self._convert_to_mp3(temp_file_path, info['title'])
            
            # Удаляем временный файл
            try:
                Path(temp_file_path).unlink(missing_ok=True)
            except Exception:
                pass
            
            if mp3_file_path and Path(mp3_file_path).exists():
                # Проверяем размер файла
                file_size = Path(mp3_file_path).stat().st_size
                if file_size > settings.MAX_FILE_SIZE * 1024 * 1024:
                    self.logger.warning(f"Скачанный файл превышает лимит размера: {file_size} байт")
                    Path(mp3_file_path).unlink(missing_ok=True)
                    return None
                
                self.logger.info(f"Успешно скачан файл: {mp3_file_path}")
                return mp3_file_path
            
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка при скачивании аудио из {url}: {e}")
            return None
    
    async def _convert_to_mp3(self, input_path: str, title: str) -> Optional[str]:
        """Конвертирует аудио файл в MP3 формат"""
        try:
            loop = asyncio.get_event_loop()
            
            def convert():
                # Генерируем имя выходного файла
                unique_id = str(uuid.uuid4())[:8]
                safe_title = re.sub(r'[^\w\s-]', '', title).strip()[:50]
                output_filename = f"{safe_title}_{unique_id}.mp3"
                output_path = settings.TEMP_DIR / output_filename
                
                # Конвертируем с помощью pydub
                audio = AudioSegment.from_file(input_path)
                
                # Настройки качества
                audio = audio.set_frame_rate(44100)
                audio = audio.set_channels(2)
                
                # Экспортируем в MP3
                audio.export(
                    str(output_path),
                    format="mp3",
                    bitrate="192k",
                    tags={
                        'title': title,
                        'artist': 'YouTube',
                        'album': 'YouTube Audio Bot'
                    }
                )
                
                return str(output_path)
            
            result = await loop.run_in_executor(None, convert)
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка при конвертации в MP3: {e}")
            return None
    
    def cleanup_temp_files(self):
        """Очищает временные файлы"""
        try:
            temp_dir = Path(settings.TEMP_DIR)
            if temp_dir.exists():
                for file in temp_dir.iterdir():
                    if file.is_file():
                        file.unlink()
                        
                self.logger.info("Временные файлы очищены")
        except Exception as e:
            self.logger.error(f"Ошибка при очистке временных файлов: {e}") 