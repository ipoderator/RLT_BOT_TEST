# Быстрый старт

## 1. Установка зависимостей

```bash
# Активируйте виртуальное окружение (если еще не активировано)
source env/bin/activate

# Установите зависимости
pip install -r requirements.txt
```

## 2. Настройка PostgreSQL

Убедитесь, что PostgreSQL установлен и запущен. Создайте базу данных:

```sql
CREATE DATABASE video_analytics;
```

## 3. Настройка переменных окружения

**Интерактивная настройка (рекомендуется):**
```bash
python setup_env.py
```

**Или создайте файл `.env` вручную:**
```bash
cp .env.example .env
```

Затем отредактируйте `.env` и заполните:
```env
TELEGRAM_BOT_TOKEN=ваш_токен_бота
GIGACHAT_CREDENTIALS=ваш_ключ_gigachat
GIGACHAT_SCOPE=GIGACHAT_API_PERS
DATABASE_URL=postgresql://user:password@localhost:5432/video_analytics
```

Где получить:
- **TELEGRAM_BOT_TOKEN**: Напишите [@BotFather](https://t.me/BotFather) в Telegram, создайте бота командой `/newbot`
- **GIGACHAT_CREDENTIALS**: Зарегистрируйтесь на [платформе разработчиков Сбера](https://developers.sber.ru/gigachat), создайте приложение и получите Authorization Key
- **GIGACHAT_SCOPE**: Область действия API (GIGACHAT_API_PERS для личного использования)
- **DATABASE_URL**: URL вашей базы данных PostgreSQL

## 4. Загрузка данных

Скачайте JSON файл с данными (ссылка должна быть предоставлена отдельно) и загрузите его:

```bash
python load_data.py путь/к/файлу.json
```

Например:
```bash
python load_data.py data.json
```

## 5. Запуск бота

```bash
python bot.py
```

После запуска вы увидите сообщение "Бот запущен...". Найдите вашего бота в Telegram и отправьте ему `/start`.

## 6. Тестирование (опционально)

Для тестирования без Telegram:

```bash
python test_bot.py
```

## Примеры вопросов для бота

- "Сколько всего видео есть в системе?"
- "Сколько видео у креатора с id creator123 вышло с 1 ноября 2025 по 5 ноября 2025 включительно?"
- "Сколько видео набрало больше 100000 просмотров за всё время?"
- "На сколько просмотров в сумме выросли все видео 28 ноября 2025?"
- "Сколько разных видео получали новые просмотры 27 ноября 2025?"

