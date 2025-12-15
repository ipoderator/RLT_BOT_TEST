# Быстрое исправление ошибок

## Проблема 1: Ошибка совместимости httpx/openai

**Ошибка:** `TypeError: Client.__init__() got an unexpected keyword argument 'proxies'`

**Быстрое исправление:**
```bash
python fix_dependencies.py
```

Или вручную:
```bash
pip install --upgrade httpx>=0.27.0
```

---

## Проблема 2: Ошибка PostgreSQL - роль не существует

**Ошибка:** `FATAL: role "postgres" does not exist`

**Быстрое исправление:**

1. Узнайте ваше имя пользователя:
   ```bash
   whoami
   ```

2. Обновите DATABASE_URL в `.env` файле:
   ```env
   DATABASE_URL=postgresql://ваш_пользователь@localhost:5432/video_analytics
   ```
   
   Например, если ваш пользователь `glebchurkin`:
   ```env
   DATABASE_URL=postgresql://glebchurkin@localhost:5432/video_analytics
   ```

3. Или создайте роль postgres:
   ```bash
   createuser -s postgres
   ```

---

## Автоматическое исправление всех проблем

Запустите скрипт для автоматического исправления:
```bash
python fix_all_issues.py
```

Этот скрипт:
- ✅ Обновит зависимости httpx
- ✅ Предложит исправление для PostgreSQL
- ✅ Покажет инструкции по дальнейшим действиям

---

## После исправления

Запустите проверки:
```bash
python run_all_tests.py
```

Скрипт `run_all_tests.py` теперь автоматически проверяет и пытается исправить проблемы с зависимостями перед запуском тестов.
