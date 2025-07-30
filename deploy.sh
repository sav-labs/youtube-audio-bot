#!/bin/bash

# YouTube Audio Bot - Deployment Script
# Этот скрипт собирает Docker образ и запускает бота

set -e

# Конфигурация
CONTAINER_NAME="youtube-audio-bot"
IMAGE_NAME="youtube-audio-bot:latest"
DATA_VOLUME="youtube-bot-data"
LOGS_VOLUME="youtube-bot-logs"

echo "🤖 YouTube Audio Bot - Deployment Script"
echo "========================================"

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден!"
    echo "📋 Создайте файл .env на основе env.example:"
    echo "   cp env.example .env"
    echo "   # Затем отредактируйте .env файл"
    exit 1
fi

# Проверяем наличие Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен!"
    echo "Установите Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

echo "🔧 Останавливаем существующий контейнер (если запущен)..."
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

echo "🏗️  Собираем Docker образ (с обновленными зависимостями)..."
docker build --no-cache -t $IMAGE_NAME .

echo "📦 Создаем volumes для данных..."
docker volume create $DATA_VOLUME 2>/dev/null || true
docker volume create $LOGS_VOLUME 2>/dev/null || true

echo "🚀 Запускаем контейнер..."
docker run -d \
    --name $CONTAINER_NAME \
    --restart unless-stopped \
    --env-file .env \
    -v $DATA_VOLUME:/app/data \
    -v $LOGS_VOLUME:/app/logs \
    $IMAGE_NAME

echo "✅ Контейнер запущен!"
echo ""
echo "📊 Информация о контейнере:"
docker ps -f name=$CONTAINER_NAME --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "📋 Полезные команды:"
echo "  Просмотр логов:      docker logs -f $CONTAINER_NAME"
echo "  Остановка:           docker stop $CONTAINER_NAME"
echo "  Запуск:              docker start $CONTAINER_NAME"
echo "  Перезапуск:          docker restart $CONTAINER_NAME"
echo "  Удаление:            docker rm -f $CONTAINER_NAME"
echo ""
echo "🎉 Развертывание завершено!" 