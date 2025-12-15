# SQL Миграции

Этот каталог содержит SQL миграции для создания и обновления схемы базы данных.

## Применение миграций

### Способ 1: Использование psql

```bash
# Подключитесь к базе данных
psql -U your_user -d video_analytics

# Примените миграцию
\i migrations/001_initial_schema.sql
```

### Способ 2: Использование Python скрипта

```bash
python -c "
from database import init_db
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv('DATABASE_URL')
if db_url:
    init_db(db_url)
    print('Таблицы созданы успешно')
else:
    print('Ошибка: DATABASE_URL не установлен')
"
```

### Способ 3: Использование SQLAlchemy (рекомендуется)

Проект использует SQLAlchemy для автоматического создания таблиц. При первом запуске бота или скрипта загрузки данных таблицы будут созданы автоматически через функцию `init_db()` из модуля `database.py`.

```python
from database import init_db
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv('DATABASE_URL')
if db_url:
    init_db(db_url)
```

## Структура миграций

- `001_initial_schema.sql` - Начальная схема базы данных:
  - Таблица `videos` - итоговая статистика по каждому видео
  - Таблица `video_snapshots` - почасовые снапшоты статистики
  - Индексы для оптимизации запросов

## Порядок применения

Миграции должны применяться в порядке их нумерации:

1. `001_initial_schema.sql` - применяется первой для создания базовой структуры

## Откат миграций

Для отката миграции `001_initial_schema.sql` выполните:

```sql
DROP TABLE IF EXISTS video_snapshots;
DROP TABLE IF EXISTS videos;
```

**Внимание:** Откат миграций приведет к удалению всех данных!

