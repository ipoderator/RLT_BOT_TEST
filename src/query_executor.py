"""
Модуль для выполнения SQL запросов и извлечения результатов.
"""
import asyncpg
from typing import Optional
from urllib.parse import urlparse
from loguru import logger
try:
    # Попытка импорта как модуль
    from src.query_generator import SQLQueryGenerator, create_generator
except ImportError:
    # Импорт для прямого запуска
    from query_generator import SQLQueryGenerator, create_generator


class VideoAnalytics:
    """Класс для работы с аналитикой видео через SQL запросы."""

    def __init__(self, db_url: str, gigachat_credentials: Optional[str] = None, gigachat_scope: Optional[str] = None):
        """
        Инициализация класса аналитики.

        Args:
            db_url: URL базы данных PostgreSQL
            gigachat_credentials: Authorization key GigaChat (опционально, можно из переменных окружения)
            gigachat_scope: Scope GigaChat API (опционально, по умолчанию GIGACHAT_API_PERS)
        """
        self.db_url = db_url
        self.pool: Optional[asyncpg.Pool] = None

        # Создаем генератор SQL
        if gigachat_credentials:
            scope = gigachat_scope or "GIGACHAT_API_PERS"
            self.query_generator = SQLQueryGenerator(gigachat_credentials, scope)
        else:
            self.query_generator = create_generator()
            if not self.query_generator:
                raise ValueError(
                    "GigaChat не настроен. Укажите GIGACHAT_CREDENTIALS "
                    "в переменных окружения или передайте их в конструктор."
                )

    async def _get_pool(self) -> asyncpg.Pool:
        """Получает или создает пул соединений с БД."""
        if self.pool is None:
            # Парсим URL для asyncpg
            # Формат: postgresql://user:password@host:port/dbname
            db_url = self.db_url

            # Убираем префикс postgresql+asyncpg:// если есть
            if db_url.startswith("postgresql+asyncpg://"):
                db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)

            # Парсим URL
            parsed = urlparse(db_url)

            if parsed.scheme not in ('postgresql', 'postgres'):
                raise ValueError(
                    f"Неверный формат DATABASE_URL: "
                    f"ожидается postgresql://, получено {parsed.scheme}://"
                )

            # Извлекаем параметры
            user = parsed.username
            password = parsed.password
            host = parsed.hostname or 'localhost'
            port = parsed.port or 5432
            database = parsed.path.lstrip('/')

            if not user or not database:
                raise ValueError(
                    "Неверный формат DATABASE_URL: "
                    "отсутствуют user или database"
                )

            self.pool = await asyncpg.create_pool(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                min_size=1,
                max_size=5
            )

        return self.pool

    def _validate_sql(self, sql: str) -> bool:
        """
        Валидирует SQL запрос на безопасность.

        Args:
            sql: SQL запрос для проверки

        Returns:
            True если запрос безопасен, False иначе
        """
        sql_upper = sql.upper().strip()

        # Запрещенные операции
        forbidden = [
            'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE',
            'TRUNCATE', 'EXEC', 'EXECUTE', 'GRANT', 'REVOKE'
        ]

        for keyword in forbidden:
            if keyword in sql_upper:
                return False

        # Разрешаем только SELECT
        if not sql_upper.startswith('SELECT'):
            return False

        return True

    async def _execute_query(self, sql: str) -> Optional[float]:
        """
        Выполняет SQL запрос и извлекает одно число из результата.

        Args:
            sql: SQL запрос

        Returns:
            Число из результата запроса или None если данных нет
        """
        pool = await self._get_pool()

        async with pool.acquire() as connection:
            try:
                result = await connection.fetch(sql)

                # COUNT, SUM и другие агрегатные функции всегда возвращают хотя бы одну строку
                # Если результат пустой, это ошибка
                if not result or len(result) == 0:
                    # Для агрегатных функций это не должно происходить, но на всякий случай
                    return 0.0

                # Извлекаем первое значение из первой строки
                if len(result[0]) > 0:
                    value = result[0][0]

                    # Преобразуем в число
                    # None может быть результатом SUM() для пустой таблицы, это валидный 0
                    if value is None:
                        return 0.0

                    if isinstance(value, (int, float)):
                        return float(value)
                    elif isinstance(value, str):
                        # Пробуем преобразовать строку в число
                        try:
                            return float(value)
                        except ValueError:
                            return 0.0
                    else:
                        try:
                            return float(value)
                        except (ValueError, TypeError):
                            return 0.0

                return 0.0

            except Exception as e:
                raise Exception(f"Ошибка при выполнении SQL запроса: {e}")

    def _format_number(self, number) -> str:
        """
        Форматирует число в строку без пробелов и символов форматирования.

        Args:
            number: Число для форматирования

        Returns:
            Число в виде строки без пробелов
        """
        if number is None:
            return "0"

        # Преобразуем в число, если это строка
        if isinstance(number, str):
            # Убираем пробелы из строки
            number = number.replace(' ', '')
            try:
                num_value = float(number)
            except (ValueError, TypeError):
                return "0"
        else:
            num_value = float(number)

        # Если число целое, возвращаем без десятичной части
        if num_value == int(num_value):
            return str(int(num_value))
        else:
            # Для десятичных чисел тоже возвращаем целое (по требованию)
            return str(int(num_value))

    async def answer_question(self, question: str) -> str:
        """
        Отвечает на вопрос пользователя, возвращая одно число.

        Args:
            question: Вопрос на русском языке

        Returns:
            Ответ в виде числа (строка) без пробелов и символов форматирования
        """
        try:
            # Генерируем SQL запрос
            sql = await self.query_generator.generate_sql(question)

            # Валидируем SQL
            if not self._validate_sql(sql):
                return "Ошибка: небезопасный SQL запрос"

            # Выполняем запрос
            result = await self._execute_query(sql)

            # Форматируем число (убираем пробелы, если есть)
            return self._format_number(result)

        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__

            # Логируем ошибку для отладки
            logger.error(
                "Ошибка при обработке вопроса",
                question=question[:200],
                error=error_msg,
                error_type=error_type
            )

            # Формируем понятное сообщение для пользователя
            if "SQL запрос" in error_msg or "SQL" in error_msg:
                # Ошибка связана с генерацией SQL
                return (
                    "Не удалось обработать ваш вопрос.\n\n"
                    "Попробуйте переформулировать вопрос более конкретно, например:\n"
                    "• Сколько всего видео в системе?\n"
                    "• Сколько просмотров у всех видео?\n"
                    "• Сколько видео набрало больше 100000 просмотров?"
                )
            elif "подключ" in error_msg.lower() or "connection" in error_msg.lower():
                # Ошибка подключения
                return (
                    "Ошибка подключения к базе данных или API.\n\n"
                    "Пожалуйста, обратитесь к администратору."
                )
            elif "GigaChat" in error_msg or "API" in error_msg:
                # Ошибка API
                return (
                    "Ошибка при обращении к API.\n\n"
                    "Попробуйте позже или обратитесь к администратору."
                )
            else:
                # Общая ошибка
                return (
                    "Произошла ошибка при обработке вопроса.\n\n"
                    "Попробуйте переформулировать вопрос или обратитесь к администратору."
                )

    async def close(self):
        """Закрывает соединения с БД."""
        if self.pool:
            await self.pool.close()
            self.pool = None
