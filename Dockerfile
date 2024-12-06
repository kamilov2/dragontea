# Используем базовый образ Python
FROM python:3.10-slim

# Устанавливаем зависимости
RUN apt-get update && apt-get install -y \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы проекта в контейнер
WORKDIR /app
COPY . /app/

# Устанавливаем зависимости Python
RUN pip install telethon asyncio requests sqlalchemy --no-cache-dir

# Команда запуска скрипта
CMD ["python", "main.py"]

