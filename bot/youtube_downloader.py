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
        # Убираем параметры плейлиста и другие
        if '&list=' in url:
            url = url.split('&list=')[0]
        if '&start_radio=' in url:
            url = url.split('&start_radio=')[0]
        return url
    
    async def get_video_info(self, url: str) -> Optional[dict]:
        """Получает информацию о видео без скачивания"""
        try:
            url = self._clean_url(url)
            loop = asyncio.get_event_loop()
            
            def extract_info():
                yt = YouTube(url)
                return {
                    'title': yt.title,
                    'duration': yt.length,
                    'author': yt.author,
                    'video_id': yt.video_id,
                    'views': yt.views,
                    'description': yt.description[:500] if yt.description else ""
                }
            
            info = await loop.run_in_executor(None, extract_info)
            return info
            
        except Exception as e:
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
            
            # Проверяем длительность видео
            duration = info.get('duration', 0)
            if duration > 7200:  # 2 часа
                self.logger.warning(f"Видео слишком длинное ({duration} сек): {url}")
                return None
            
            # Скачиваем аудио
            loop = asyncio.get_event_loop()
            
            def download():
                yt = YouTube(url)
                
                # Получаем лучший аудио поток
                audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').first()
                
                if not audio_stream:
                    # Если нет аудио потока, берем видео с аудио
                    audio_stream = yt.streams.filter(adaptive=True, file_extension='mp4', only_audio=True).first()
                
                if not audio_stream:
                    self.logger.error("Не удалось найти аудио поток")
                    return None
                
                # Генерируем уникальное имя файла
                unique_id = str(uuid.uuid4())[:8]
                safe_title = re.sub(r'[^\w\s-]', '', info['title']).strip()[:50]
                temp_filename = f"{safe_title}_{unique_id}"
                
                # Скачиваем во временную директорию
                temp_path = settings.TEMP_DIR / f"{temp_filename}.mp4"
                audio_stream.download(output_path=settings.TEMP_DIR, filename=f"{temp_filename}.mp4")
                
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