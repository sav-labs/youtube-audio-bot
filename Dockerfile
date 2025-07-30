# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Создаем пользователя для запуска приложения
RUN useradd --create-home --shell /bin/bash app

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем необходимые директории
RUN mkdir -p logs data downloads temp \
    && chown -R app:app /app

# Переключаемся на пользователя app
USER app

# Создаем volume для данных
VOLUME ["/app/data", "/app/logs"]

# Открываем порт (если будет нужен в будущем)
EXPOSE 8000

# Команда запуска
CMD ["python", "main.py"] 