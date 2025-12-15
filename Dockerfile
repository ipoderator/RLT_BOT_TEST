# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости для PostgreSQL
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код приложения
COPY . .

# Создаем директории для логов и кэша
RUN mkdir -p logs cache

# Устанавливаем переменные окружения по умолчанию
ENV PYTHONUNBUFFERED=1
ENV AUTO_RELOAD=true

# Команда запуска бота
# Используем скрипт автоперезагрузки если AUTO_RELOAD=true
# Для продакшена установите AUTO_RELOAD=false
CMD ["sh", "-c", "if [ \"$AUTO_RELOAD\" = \"true\" ]; then python scripts/watch_bot.py; else python -m src.bot; fi"]

