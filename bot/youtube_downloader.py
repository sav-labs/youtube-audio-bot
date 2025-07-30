import re
import logging
import asyncio
from pathlib import Path
from typing import Optional
import yt_dlp
from settings import settings


class YouTubeDownloader:
    """Класс для скачивания аудио из YouTube видео"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Настройки yt-dlp
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': str(settings.TEMP_DIR / '%(title)s.%(ext)s'),
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'extractflat': False,
            'writethumbnail': False,
            'writeinfojson': False,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    
    def is_valid_youtube_url(self, url: str) -> bool:
        """Проверяет, является ли URL корректной ссылкой на YouTube"""
        youtube_regex = re.compile(
            r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
            r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
        )
        
        return bool(youtube_regex.match(url))
    
    async def get_video_info(self, url: str) -> Optional[dict]:
        """Получает информацию о видео без скачивания"""
        try:
            loop = asyncio.get_event_loop()
            
            def extract_info():
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)
            
            info = await loop.run_in_executor(None, extract_info)
            return info
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении информации о видео {url}: {e}")
            return None
    
    async def download_audio(self, url: str) -> Optional[str]:
        """Скачивает аудио из YouTube видео и возвращает путь к файлу"""
        try:
            # Получаем информацию о видео
            info = await self.get_video_info(url)
            if not info:
                self.logger.error(f"Не удалось получить информацию о видео: {url}")
                return None
            
            # Проверяем размер видео
            duration = info.get('duration', 0)
            if duration > 7200:  # 2 часа
                self.logger.warning(f"Видео слишком длинное ({duration} сек): {url}")
                return None
            
            # Проверяем приблизительный размер файла
            filesize = info.get('filesize') or info.get('filesize_approx')
            if filesize and filesize > settings.MAX_FILE_SIZE * 1024 * 1024:
                self.logger.warning(f"Файл слишком большой ({filesize} байт): {url}")
                return None
            
            # Скачиваем аудио
            loop = asyncio.get_event_loop()
            
            def download():
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    ydl.download([url])
                    return self._find_downloaded_file(info.get('title', 'audio'))
            
            file_path = await loop.run_in_executor(None, download)
            
            if file_path and Path(file_path).exists():
                # Проверяем размер скачанного файла
                file_size = Path(file_path).stat().st_size
                if file_size > settings.MAX_FILE_SIZE * 1024 * 1024:
                    self.logger.warning(f"Скачанный файл превышает лимит размера: {file_size} байт")
                    Path(file_path).unlink(missing_ok=True)
                    return None
                
                self.logger.info(f"Успешно скачан файл: {file_path}")
                return file_path
            
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка при скачивании аудио из {url}: {e}")
            return None
    
    def _find_downloaded_file(self, title: str) -> Optional[str]:
        """Находит скачанный файл в временной директории"""
        try:
            # Очищаем название для поиска файла
            clean_title = re.sub(r'[^\w\s-]', '', title).strip()
            
            # Ищем файлы в временной директории
            temp_dir = Path(settings.TEMP_DIR)
            
            # Ищем по точному совпадению
            for pattern in [f"{clean_title}.mp3", f"*{clean_title}*.mp3", "*.mp3"]:
                files = list(temp_dir.glob(pattern))
                if files:
                    # Возвращаем самый новый файл
                    return str(max(files, key=lambda x: x.stat().st_mtime))
            
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка при поиске скачанного файла: {e}")
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