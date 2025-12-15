# Устранение проблем

## Проблема 1: TypeError с 'proxies' в OpenAI клиенте

**Ошибка:**
```
TypeError: Client.__init__() got an unexpected keyword argument 'proxies'
```

**Причина:**
Несовместимость версий библиотек `httpx` и `openai`. Версия `openai==1.3.5` требует `httpx>=0.27.0`.

**Решение:**

### Автоматическое исправление:
```bash
python fix_dependencies.py
```

### Ручное исправление:
```bash
pip install --upgrade httpx>=0.27.0
```

Или переустановите все зависимости:
```bash
pip install --upgrade -r requirements.txt
```

---

## Проблема 2: Ошибка подключения к PostgreSQL - роль не существует

**Ошибка:**
```
FATAL: role "postgres" does not exist
```

**Причина:**
В системе PostgreSQL нет пользователя с именем "postgres", который указан в `DATABASE_URL`.

**Решения:**

### Вариант 1: Использовать существующего пользователя

1. Узнайте имя вашего пользователя PostgreSQL:
   ```bash
   whoami
   # или
   psql -l
   ```

2. Обновите `DATABASE_URL` в `.env` файле:
   ```env
   DATABASE_URL=postgresql://ваш_пользователь@localhost:5432/video_analytics
   ```
   
   Например, если ваш пользователь `glebchurkin`:
   ```env
   DATABASE_URL=postgresql://glebchurkin@localhost:5432/video_analytics
   ```

### Вариант 2: Создать роль "postgres"

```bash
createuser -s postgres
```

### Вариант 3: Создать нового пользователя и базу данных

```bash
# Создать пользователя
createuser -s ваш_пользователь

# Создать базу данных
createdb -O ваш_пользователь video_analytics

# Обновить DATABASE_URL в .env
```

---

## Проблема 3: PostgreSQL не запущен

**Ошибка:**
```
connection to server at "localhost" (::1), port 5432 failed
```

**Решение:**

### macOS (Homebrew):
```bash
# Запустить PostgreSQL
brew services start postgresql@14
# или
brew services start postgresql
```

### Linux:
```bash
# Ubuntu/Debian
sudo systemctl start postgresql

# или
sudo service postgresql start
```

### Проверка:
```bash
psql --version
psql -l
```

---

## Проблема 4: База данных не существует

**Ошибка:**
```
database "video_analytics" does not exist
```

**Решение:**

Создайте базу данных:
```bash
createdb video_analytics
```

Или через psql:
```bash
psql -c "CREATE DATABASE video_analytics;"
```

---

## Проблема 5: Неверный формат DATABASE_URL

**Правильный формат:**
```
postgresql://user:password@host:port/database_name
```

**Примеры:**

1. Локальная БД с паролем:
   ```env
   DATABASE_URL=postgresql://postgres:mypassword@localhost:5432/video_analytics
   ```

2. Локальная БД без пароля (peer authentication):
   ```env
   DATABASE_URL=postgresql://glebchurkin@localhost:5432/video_analytics
   ```

3. Удаленная БД:
   ```env
   DATABASE_URL=postgresql://user:password@example.com:5432/video_analytics
   ```

---

## Быстрая диагностика

Запустите скрипт диагностики:
```bash
python run_all_tests.py
```

Он покажет:
- Какие переменные окружения не настроены
- Какие зависимости отсутствуют
- Проблемы с подключением к БД

---

## Полная переустановка зависимостей

Если проблемы продолжаются:

```bash
# Удалить виртуальное окружение
rm -rf env

# Создать новое
python3 -m venv env

# Активировать
source env/bin/activate  # macOS/Linux
# или
env\Scripts\activate  # Windows

# Установить зависимости
pip install --upgrade pip
pip install -r requirements.txt

# Исправить совместимость
python fix_dependencies.py
```

---

## Получение помощи

Если проблема не решена:

1. Проверьте логи ошибок в терминале
2. Убедитесь, что все переменные окружения настроены
3. Проверьте версии Python и PostgreSQL
4. Убедитесь, что все зависимости установлены

Для проверки окружения:
```bash
python run_all_tests.py
```
