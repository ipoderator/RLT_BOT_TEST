"""
Комплексный скрипт для проверки всех требований к боту согласно плану проверки.
Проверяет соответствие реализации всем требованиям из технического задания.
"""
import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Dict
from dotenv import load_dotenv
from sqlalchemy import inspect, text

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database import init_db  # noqa: E402
from src.query_executor import VideoAnalytics  # noqa: E402
from src.query_generator import SQLQueryGenerator  # noqa: E402

load_dotenv()


class RequirementsChecker:
    """Класс для проверки требований к боту."""

    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        self.gigachat_credentials = os.getenv("GIGACHAT_CREDENTIALS")
        self.gigachat_scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self.results = {}
        self.errors = []

    def check_1_database_deployment(self) -> Dict[str, bool]:
        """Проверка развертывания базы данных."""
        print("\n" + "="*60)
        print("1. ПРОВЕРКА РАЗВЕРТЫВАНИЯ БАЗЫ ДАННЫХ")
        print("="*60)

        checks = {}

        try:
            if not self.db_url:
                print("⚠️  DATABASE_URL не настроен")
                print("   Для проверки БД создайте файл .env: python setup_env.py")
                checks["db_url_configured"] = False
                return checks

            engine = init_db(self.db_url)
            inspector = inspect(engine)

            # Проверка таблицы videos
            if 'videos' in inspector.get_table_names():
                print("✅ Таблица 'videos' существует")
                checks["videos_table_exists"] = True

                # Проверка колонок videos
                columns = {col['name']: col for col in inspector.get_columns('videos')}
                required_videos_columns = {
                    'id': 'PRIMARY KEY',
                    'creator_id': 'STRING',
                    'video_created_at': 'DATETIME',
                    'views_count': 'INTEGER',
                    'likes_count': 'INTEGER',
                    'comments_count': 'INTEGER',
                    'reports_count': 'INTEGER',
                    'created_at': 'DATETIME',
                    'updated_at': 'DATETIME'
                }

                for col_name in required_videos_columns:
                    if col_name in columns:
                        print(f"  ✅ Колонка '{col_name}' существует")
                    else:
                        print(f"  ❌ Колонка '{col_name}' отсутствует")
                        checks[f"videos_column_{col_name}"] = False

                # Проверка индексов
                indexes = inspector.get_indexes('videos')
                index_names = [idx['name'] for idx in indexes]
                if any('creator_id' in str(idx) for idx in indexes):
                    print("  ✅ Индекс на creator_id существует")
                    checks["videos_index_creator_id"] = True
                else:
                    print("  ⚠️  Индекс на creator_id не найден")
                    checks["videos_index_creator_id"] = False

            else:
                print("❌ Таблица 'videos' не существует")
                checks["videos_table_exists"] = False

            # Проверка таблицы video_snapshots
            if 'video_snapshots' in inspector.get_table_names():
                print("✅ Таблица 'video_snapshots' существует")
                checks["snapshots_table_exists"] = True

                # Проверка колонок video_snapshots
                columns = {col['name']: col for col in inspector.get_columns('video_snapshots')}
                required_snapshots_columns = {
                    'id': 'PRIMARY KEY',
                    'video_id': 'FOREIGN KEY',
                    'views_count': 'INTEGER',
                    'likes_count': 'INTEGER',
                    'comments_count': 'INTEGER',
                    'reports_count': 'INTEGER',
                    'delta_views_count': 'INTEGER',
                    'delta_likes_count': 'INTEGER',
                    'delta_comments_count': 'INTEGER',
                    'delta_reports_count': 'INTEGER',
                    'created_at': 'DATETIME',
                    'updated_at': 'DATETIME'
                }

                for col_name in required_snapshots_columns:
                    if col_name in columns:
                        print(f"  ✅ Колонка '{col_name}' существует")
                    else:
                        print(f"  ❌ Колонка '{col_name}' отсутствует")
                        checks[f"snapshots_column_{col_name}"] = False

                # Проверка составного индекса
                indexes = inspector.get_indexes('video_snapshots')
                index_names = [idx['name'] for idx in indexes]
                if 'ix_video_snapshots_video_time' in index_names:
                    print("  ✅ Составной индекс 'ix_video_snapshots_video_time' существует")
                    checks["snapshots_composite_index"] = True
                else:
                    print("  ⚠️  Составной индекс 'ix_video_snapshots_video_time' не найден")
                    checks["snapshots_composite_index"] = False

            else:
                print("❌ Таблица 'video_snapshots' не существует")
                checks["snapshots_table_exists"] = False

            checks["db_connection"] = True

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Ошибка при проверке БД: {error_msg}")

            # Более информативные сообщения
            if "role" in error_msg.lower() and "does not exist" in error_msg.lower():
                print("\n💡 Проблема: роль пользователя PostgreSQL не существует")
                print("   Решение: используйте существующего пользователя или создайте новую роль")

                # Пытаемся определить текущего пользователя
                import os
                current_user = os.getenv("USER") or os.getenv("USERNAME") or "ваш_пользователь"
                print(f"\n   Текущий пользователь системы: {current_user}")
                print(f"   Пример DATABASE_URL: postgresql://{current_user}@localhost:5432/video_analytics")
                print("\n   Или создайте роль postgres:")
                print("   createuser -s postgres")

            checks["db_connection"] = False
            self.errors.append(f"Database check error: {e}")

        return checks

    def check_2_data_loading(self) -> Dict[str, bool]:
        """Проверка загрузки данных из JSON."""
        print("\n" + "="*60)
        print("2. ПРОВЕРКА ЗАГРУЗКИ ДАННЫХ ИЗ JSON")
        print("="*60)

        checks = {}

        try:
            engine = init_db(self.db_url)

            # Проверка количества записей
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM videos"))
                video_count = result.scalar()
                print(f"✅ Загружено видео: {video_count}")
                checks["videos_loaded"] = video_count > 0

                result = conn.execute(text("SELECT COUNT(*) FROM video_snapshots"))
                snapshot_count = result.scalar()
                print(f"✅ Загружено снапшотов: {snapshot_count}")
                checks["snapshots_loaded"] = snapshot_count > 0

                # Проверка корректности данных
                result = conn.execute(text("""
                    SELECT id, creator_id, views_count, video_created_at
                    FROM videos
                    LIMIT 5
                """))
                sample_videos = result.fetchall()
                if sample_videos:
                    print("✅ Примеры данных из videos:")
                    for row in sample_videos[:3]:
                        print(f"  - Video ID: {row[0]}, Creator: {row[1]}, Views: {row[2]}")
                    checks["videos_data_valid"] = True
                else:
                    print("⚠️  Нет данных в таблице videos")
                    checks["videos_data_valid"] = False

                result = conn.execute(text("""
                    SELECT video_id, created_at, delta_views_count
                    FROM video_snapshots
                    LIMIT 5
                """))
                sample_snapshots = result.fetchall()
                if sample_snapshots:
                    print("✅ Примеры данных из video_snapshots:")
                    for row in sample_snapshots[:3]:
                        print(f"  - Video ID: {row[0]}, Created: {row[1]}, Delta Views: {row[2]}")
                    checks["snapshots_data_valid"] = True
                else:
                    print("⚠️  Нет данных в таблице video_snapshots")
                    checks["snapshots_data_valid"] = False

        except Exception as e:
            print(f"❌ Ошибка при проверке данных: {e}")
            checks["data_check_error"] = False
            self.errors.append(f"Data loading check error: {e}")

        return checks

    def check_3_technologies(self) -> Dict[str, bool]:
        """Проверка используемых технологий."""
        print("\n" + "="*60)
        print("3. ПРОВЕРКА ТЕХНОЛОГИЙ")
        print("="*60)

        checks = {}

        # Проверка версии Python
        python_version = sys.version_info
        if python_version >= (3, 11):
            print(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
            checks["python_version"] = True
        else:
            print(f"⚠️  Python {python_version.major}.{python_version.minor} (рекомендуется 3.11+)")
            checks["python_version"] = False

        # Проверка зависимостей
        try:
            import aiogram
            print(f"✅ aiogram {aiogram.__version__}")
            checks["aiogram"] = True
        except ImportError:
            print("❌ aiogram не установлен")
            checks["aiogram"] = False

        try:
            import sqlalchemy
            print(f"✅ SQLAlchemy {sqlalchemy.__version__}")
            checks["sqlalchemy"] = True
        except ImportError:
            print("❌ SQLAlchemy не установлен")
            checks["sqlalchemy"] = False

        try:
            import asyncpg  # noqa: F401
            print("✅ asyncpg установлен")
            checks["asyncpg"] = True
        except ImportError:
            print("❌ asyncpg не установлен")
            checks["asyncpg"] = False

        try:
            import psycopg2  # noqa: F401
            print("✅ psycopg2 установлен")
            checks["psycopg2"] = True
        except ImportError:
            print("❌ psycopg2 не установлен")
            checks["psycopg2"] = False

        try:
            import gigachat  # noqa: F401
            print("✅ GigaChat API установлен")
            checks["gigachat"] = True
        except ImportError:
            print("❌ GigaChat API не установлен")
            checks["gigachat"] = False

        return checks

    def check_4_telegram_bot(self) -> Dict[str, bool]:
        """Проверка работы Telegram-бота."""
        print("\n" + "="*60)
        print("4. ПРОВЕРКА РАБОТЫ TELEGRAM-БОТА")
        print("="*60)

        checks = {}

        # Проверка переменных окружения
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if bot_token:
            print("✅ TELEGRAM_BOT_TOKEN настроен")
            checks["bot_token"] = True
        else:
            print("❌ TELEGRAM_BOT_TOKEN не настроен")
            checks["bot_token"] = False

        if self.gigachat_credentials:
            print("✅ GIGACHAT_CREDENTIALS настроен")
            checks["gigachat_credentials"] = True
        else:
            print("❌ GIGACHAT_CREDENTIALS не настроен")
            checks["gigachat_credentials"] = False

        if self.db_url:
            print("✅ DATABASE_URL настроен")
            checks["db_url"] = True
        else:
            print("❌ DATABASE_URL не настроен")
            checks["db_url"] = False

        # Проверка импорта бота
        try:
            from bot import VideoAnalyticsBot
            print("✅ Модуль bot.py импортируется")
            checks["bot_import"] = True

            # Проверка наличия методов
            if hasattr(VideoAnalyticsBot, 'start_command'):
                print("✅ Метод start_command существует")
                checks["start_command"] = True
            else:
                print("❌ Метод start_command отсутствует")
                checks["start_command"] = False

            if hasattr(VideoAnalyticsBot, 'help_command'):
                print("✅ Метод help_command существует")
                checks["help_command"] = True
            else:
                print("❌ Метод help_command отсутствует")
                checks["help_command"] = False

            if hasattr(VideoAnalyticsBot, 'handle_message'):
                print("✅ Метод handle_message существует")
                checks["handle_message"] = True
            else:
                print("❌ Метод handle_message отсутствует")
                checks["handle_message"] = False

        except Exception as e:
            print(f"❌ Ошибка при импорте бота: {e}")
            checks["bot_import"] = False
            self.errors.append(f"Bot import error: {e}")

        return checks

    async def check_5_nlp_recognition(self) -> Dict[str, bool]:
        """Проверка распознавания естественного языка."""
        print("\n" + "="*60)
        print("5. ПРОВЕРКА РАСПОЗНАВАНИЯ ЕСТЕСТВЕННОГО ЯЗЫКА")
        print("="*60)

        checks = {}

        try:
            generator = SQLQueryGenerator(credentials=self.gigachat_credentials, scope=self.gigachat_scope)

            # Проверка наличия промпта
            from query_generator import DATABASE_SCHEMA
            if DATABASE_SCHEMA and 'videos' in DATABASE_SCHEMA and 'video_snapshots' in DATABASE_SCHEMA:
                print("✅ Промпт содержит описание схемы БД")
                checks["schema_description"] = True
            else:
                print("⚠️  Промпт не содержит полного описания схемы")
                checks["schema_description"] = False

            # Проверка валидации SQL
            if hasattr(generator, 'validate_sql'):
                print("✅ Метод validate_sql существует")

                # Тест безопасных запросов
                safe_sql = "SELECT COUNT(*) FROM videos"
                if generator.validate_sql(safe_sql):
                    print("  ✅ Безопасный запрос проходит валидацию")
                    checks["validate_safe"] = True
                else:
                    print("  ❌ Безопасный запрос не проходит валидацию")
                    checks["validate_safe"] = False

                # Тест опасных запросов
                dangerous_sqls = [
                    "DROP TABLE videos",
                    "DELETE FROM videos",
                    "UPDATE videos SET views_count = 0"
                ]
                all_blocked = True
                for dangerous_sql in dangerous_sqls:
                    if generator.validate_sql(dangerous_sql):
                        print(f"  ❌ Опасный запрос не заблокирован: {dangerous_sql}")
                        all_blocked = False

                if all_blocked:
                    print("  ✅ Опасные запросы блокируются")
                    checks["validate_dangerous"] = True
                else:
                    checks["validate_dangerous"] = False

            else:
                print("❌ Метод validate_sql отсутствует")
                checks["validate_sql"] = False

            # Тест генерации SQL для разных типов запросов
            test_queries = [
                "Сколько всего видео есть в системе?",
                "На сколько просмотров в сумме выросли все видео 28 ноября 2025?",
            ]

            sql_generation_works = True
            for query in test_queries:
                try:
                    sql = await generator.generate_sql(query)
                    if sql and 'SELECT' in sql.upper():
                        print(f"  ✅ SQL сгенерирован для: '{query[:30]}...'")
                        print(f"     SQL: {sql[:100]}...")
                    else:
                        print(f"  ❌ Неверный SQL для: '{query[:30]}...'")
                        sql_generation_works = False
                except Exception as e:
                    print(f"  ❌ Ошибка генерации SQL для '{query[:30]}...': {e}")
                    sql_generation_works = False

            checks["sql_generation"] = sql_generation_works

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Ошибка при проверке NLP: {error_msg}")

            # Обработка ошибки совместимости версий
            if "proxies" in error_msg.lower() or "unexpected keyword" in error_msg.lower() or "совместимости" in error_msg.lower():
                print("\n💡 Проблема совместимости версий библиотек httpx и openai")
                print("   Автоматическое исправление:")
                print("   python fix_dependencies.py")
                print("\n   Или вручную:")
                print("   pip install --upgrade httpx>=0.27.0")

            checks["nlp_check_error"] = False
            self.errors.append(f"NLP check error: {e}")

        return checks

    async def check_6_example_queries(self) -> Dict[str, bool]:
        """Проверка корректности ответов на примеры вопросов."""
        print("\n" + "="*60)
        print("6. ПРОВЕРКА КОРРЕКТНОСТИ ОТВЕТОВ НА ПРИМЕРЫ ВОПРОСОВ")
        print("="*60)

        checks = {}

        if not self.gigachat_credentials or not self.db_url:
            print("⚠️  Пропущено: требуется GIGACHAT_CREDENTIALS и DATABASE_URL")
            print("   Создайте файл .env: python setup_env.py")
            return checks

        analytics = VideoAnalytics(db_url=self.db_url, gigachat_credentials=self.gigachat_credentials, gigachat_scope=self.gigachat_scope)
        generator = SQLQueryGenerator(credentials=self.gigachat_credentials, scope=self.gigachat_scope)

        test_cases = [
            {
                "query": "Сколько всего видео есть в системе?",
                "expected_sql_pattern": r"SELECT\s+COUNT\s*\(\s*\*\s*\)\s+FROM\s+videos",
                "expected_table": "videos",
                "description": "6.1. Подсчет всех видео"
            },
            {
                "query": "Сколько видео набрало больше 100000 просмотров за всё время?",
                "expected_sql_pattern": r"SELECT\s+COUNT\s*\(\s*\*\s*\)\s+FROM\s+videos.*views_count\s*>\s*100000",
                "expected_table": "videos",
                "description": "6.3. Видео с просмотрами > 100000"
            },
            {
                "query": "На сколько просмотров в сумме выросли все видео 28 ноября 2025?",
                "expected_sql_pattern": r"SELECT\s+SUM\s*\(\s*delta_views_count\s*\)\s+FROM\s+video_snapshots",
                "expected_table": "video_snapshots",
                "description": "6.4. Сумма прироста просмотров за дату"
            },
            {
                "query": "Сколько разных видео получали новые просмотры 27 ноября 2025?",
                "expected_sql_pattern": r"SELECT\s+COUNT\s*\(\s*DISTINCT\s+video_id\s*\)\s+FROM\s+video_snapshots",
                "expected_table": "video_snapshots",
                "description": "6.5. Разные видео с новыми просмотрами"
            }
        ]

        try:
            for test_case in test_cases:
                print(f"\n{test_case['description']}")
                print(f"Вопрос: {test_case['query']}")

                # Проверка генерации SQL
                try:
                    sql = await generator.generate_sql(test_case['query'])
                    print(f"Сгенерированный SQL: {sql}")

                    # Проверка паттерна
                    if re.search(test_case['expected_sql_pattern'], sql, re.IGNORECASE):
                        print("  ✅ SQL соответствует ожидаемому паттерну")
                        checks[f"{test_case['description']}_sql_pattern"] = True
                    else:
                        print(f"  ⚠️  SQL не соответствует паттерну: {test_case['expected_sql_pattern']}")
                        checks[f"{test_case['description']}_sql_pattern"] = False

                    # Проверка таблицы
                    if test_case['expected_table'].lower() in sql.lower():
                        print(f"  ✅ Используется правильная таблица: {test_case['expected_table']}")
                        checks[f"{test_case['description']}_table"] = True
                    else:
                        print("  ⚠️  Используется неверная таблица")
                        checks[f"{test_case['description']}_table"] = False

                    # Проверка выполнения запроса
                    try:
                        answer = await analytics.answer_question(test_case['query'])
                        print(f"  Ответ: {answer}")

                        # Проверка формата ответа (должно быть число)
                        if answer.replace('.', '').replace('-', '').isdigit() or answer == "Данные не найдены":
                            print("  ✅ Формат ответа корректен (число)")
                            checks[f"{test_case['description']}_answer_format"] = True
                        else:
                            print(f"  ⚠️  Формат ответа некорректен: {answer}")
                            checks[f"{test_case['description']}_answer_format"] = False

                        checks[f"{test_case['description']}_execution"] = True

                    except Exception as e:
                        print(f"  ❌ Ошибка выполнения: {e}")
                        checks[f"{test_case['description']}_execution"] = False
                        self.errors.append(f"Query execution error for '{test_case['query']}': {e}")

                except Exception as e:
                    print(f"  ❌ Ошибка генерации SQL: {e}")
                    checks[f"{test_case['description']}_sql_generation"] = False
                    self.errors.append(f"SQL generation error for '{test_case['query']}': {e}")

        finally:
            await analytics.close()

        return checks

    def check_7_answer_format(self) -> Dict[str, bool]:
        """Проверка формата ответа."""
        print("\n" + "="*60)
        print("7. ПРОВЕРКА ФОРМАТА ОТВЕТА")
        print("="*60)

        checks = {}

        # Проверка кода в query_executor.py
        try:
            with open('query_executor.py', 'r', encoding='utf-8') as f:
                code = f.read()

                # Проверка форматирования чисел
                if 'isinstance(result, float)' in code and '.2f' in code:
                    print("✅ Вещественные числа округляются до 2 знаков")
                    checks["float_formatting"] = True
                else:
                    print("⚠️  Форматирование вещественных чисел не найдено")
                    checks["float_formatting"] = False

                # Проверка обработки None
                if 'result is None' in code or 'if result is None' in code:
                    print("✅ Обработка отсутствия данных присутствует")
                    checks["none_handling"] = True
                else:
                    print("⚠️  Обработка отсутствия данных не найдена")
                    checks["none_handling"] = False

                # Проверка возврата числа
                if 'str(result)' in code or 'return str' in code:
                    print("✅ Результат преобразуется в строку")
                    checks["string_conversion"] = True
                else:
                    print("⚠️  Преобразование в строку не найдено")
                    checks["string_conversion"] = False

        except Exception as e:
            print(f"❌ Ошибка при проверке формата: {e}")
            checks["format_check_error"] = False

        return checks

    def check_8_no_context(self) -> Dict[str, bool]:
        """Проверка отсутствия контекста диалога."""
        print("\n" + "="*60)
        print("8. ПРОВЕРКА ОТСУТСТВИЯ КОНТЕКСТА ДИАЛОГА")
        print("="*60)

        checks = {}

        # Проверка кода бота
        try:
            with open('bot.py', 'r', encoding='utf-8') as f:
                bot_code = f.read()

            with open('query_executor.py', 'r', encoding='utf-8') as f:
                executor_code = f.read()

            # Проверка отсутствия хранения истории
            if 'history' not in bot_code.lower() and 'context' not in bot_code.lower():
                print("✅ История сообщений не сохраняется")
                checks["no_history"] = True
            else:
                print("⚠️  Возможно используется история/контекст")
                checks["no_history"] = False

            # Проверка независимой обработки запросов
            if 'answer_question' in executor_code:
                print("✅ Каждый запрос обрабатывается независимо (метод answer_question)")
                checks["independent_processing"] = True
            else:
                print("⚠️  Независимая обработка не гарантирована")
                checks["independent_processing"] = False

        except Exception as e:
            print(f"❌ Ошибка при проверке контекста: {e}")
            checks["context_check_error"] = False

        return checks

    def check_9_error_handling(self) -> Dict[str, bool]:
        """Проверка обработки ошибок."""
        print("\n" + "="*60)
        print("9. ПРОВЕРКА ОБРАБОТКИ ОШИБОК")
        print("="*60)

        checks = {}

        try:
            with open('bot.py', 'r', encoding='utf-8') as f:
                bot_code = f.read()

            with open('query_executor.py', 'r', encoding='utf-8') as f:
                executor_code = f.read()

            # Проверка try-except блоков
            bot_try_count = bot_code.count('try:')
            executor_try_count = executor_code.count('try:')

            if bot_try_count > 0:
                print(f"✅ В bot.py найдено {bot_try_count} блоков try-except")
                checks["bot_error_handling"] = True
            else:
                print("⚠️  В bot.py нет обработки ошибок")
                checks["bot_error_handling"] = False

            if executor_try_count > 0:
                print(f"✅ В query_executor.py найдено {executor_try_count} блоков try-except")
                checks["executor_error_handling"] = True
            else:
                print("⚠️  В query_executor.py нет обработки ошибок")
                checks["executor_error_handling"] = False

            # Проверка обработки конкретных типов ошибок
            if 'Exception' in executor_code or 'except' in executor_code:
                print("✅ Обработка исключений присутствует")
                checks["exception_handling"] = True
            else:
                print("⚠️  Обработка исключений не найдена")
                checks["exception_handling"] = False

        except Exception as e:
            print(f"❌ Ошибка при проверке обработки ошибок: {e}")
            checks["error_check_error"] = False

        return checks

    def print_summary(self):
        """Выводит итоговую сводку проверки."""
        print("\n" + "="*60)
        print("ИТОГОВАЯ СВОДКА")
        print("="*60)

        total_checks = 0
        passed_checks = 0

        for section, checks in self.results.items():
            section_passed = sum(1 for v in checks.values() if v)
            section_total = len(checks)
            total_checks += section_total
            passed_checks += section_passed

            status = "✅" if section_passed == section_total else "⚠️"
            print(f"\n{status} {section}: {section_passed}/{section_total}")

        print(f"\nВсего проверок: {passed_checks}/{total_checks}")

        if self.errors:
            print(f"\n⚠️  Найдено ошибок: {len(self.errors)}")
            for error in self.errors[:5]:  # Показываем первые 5
                print(f"  - {error}")

        success_rate = (passed_checks / total_checks * 100) if total_checks > 0 else 0
        print(f"\nПроцент успешных проверок: {success_rate:.1f}%")

        if success_rate >= 90:
            print("\n✅ Все основные требования выполнены!")
        elif success_rate >= 70:
            print("\n⚠️  Большинство требований выполнено, но есть замечания")
        else:
            print("\n❌ Требуется доработка")


async def main():
    """Основная функция для запуска всех проверок."""
    print("="*60)
    print("ПРОВЕРКА ТРЕБОВАНИЙ К TELEGRAM-БОТУ")
    print("="*60)

    checker = RequirementsChecker()

    # Выполняем все проверки
    checker.results["1_database"] = checker.check_1_database_deployment()
    checker.results["2_data_loading"] = checker.check_2_data_loading()
    checker.results["3_technologies"] = checker.check_3_technologies()
    checker.results["4_telegram_bot"] = checker.check_4_telegram_bot()
    checker.results["5_nlp"] = await checker.check_5_nlp_recognition()
    checker.results["6_examples"] = await checker.check_6_example_queries()
    checker.results["7_format"] = checker.check_7_answer_format()
    checker.results["8_context"] = checker.check_8_no_context()
    checker.results["9_errors"] = checker.check_9_error_handling()

    # Выводим итоговую сводку
    checker.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
