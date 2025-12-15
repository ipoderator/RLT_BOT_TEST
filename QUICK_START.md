# Быстрый старт

## Запуск через Docker (рекомендуется)

### 1. Подготовка

```bash
# Клонируйте репозиторий
git clone <repository_url>
cd rlt

# Создайте файл .env
cp .env.example .env
```

### 2. Настройка переменных окружения

Отредактируйте `.env` файл:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GIGACHAT_CREDENTIALS=your_gigachat_credentials
GIGACHAT_SCOPE=GIGACHAT_API_PERS
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=video_analytics
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/video_analytics
```

### 3. Запуск

```bash
# Запуск всех сервисов
docker-compose up -d

# Применение миграций БД
docker-compose exec bot python -c "from database import init_db; import os; from dotenv import load_dotenv; load_dotenv(); init_db(os.getenv('DATABASE_URL'))"

# Просмотр логов
docker-compose logs -f bot
```

### 4. Загрузка данных (опционально)

```bash
# Загрузка данных из JSON файла
docker-compose exec bot python scripts/load_data.py <path_to_file.json>
```

## Запуск без Docker

### 1. Установка зависимостей

```bash
# Создание виртуального окружения
python3 -m venv env
source env/bin/activate  # Linux/Mac
# или
env\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt
```

### 2. Настройка окружения

```bash
# Интерактивная настройка
python scripts/setup_env.py

# Или вручную создайте .env файл
```

### 3. Настройка PostgreSQL

```sql
CREATE DATABASE video_analytics;
```

### 4. Применение миграций

```bash
python -c "from src.database import init_db; import os; from dotenv import load_dotenv; load_dotenv(); init_db(os.getenv('DATABASE_URL'))"
```

### 5. Загрузка данных

```bash
python scripts/load_data.py <path_to_file.json>
```

### 6. Запуск бота

```bash
python -m src.bot
```

## Проверка работы

1. Найдите вашего бота в Telegram
2. Отправьте команду `/start`
3. Задайте вопрос: "Сколько всего видео есть в системе?"

## Полезные команды

### Docker

```bash
# Просмотр статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f bot

# Остановка
docker-compose down

# Перезапуск
docker-compose restart bot
```

### Тестирование

```bash
# Запуск всех тестов
python tests/run_all_tests.py

# Отдельные тесты
python tests/test_bot.py
python tests/test_sql_generation.py
python tests/test_database_structure.py
```

## Устранение проблем

### Бот не отвечает

1. Проверьте логи: `docker-compose logs bot`
2. Убедитесь, что переменные окружения настроены правильно
3. Проверьте подключение к БД

### Ошибки подключения к БД

1. Убедитесь, что PostgreSQL запущен
2. Проверьте DATABASE_URL в .env
3. Проверьте доступность порта 5432

### Ошибки GigaChat API

1. Проверьте GIGACHAT_CREDENTIALS
2. Убедитесь, что scope правильный (GIGACHAT_API_PERS для личного использования)
3. Проверьте квоты API

## Дополнительная документация

- [ARCHITECTURE.md](ARCHITECTURE.md) - Архитектура системы
- [COMPONENTS.md](COMPONENTS.md) - Описание компонентов
- [README.md](README.md) - Полная документация

