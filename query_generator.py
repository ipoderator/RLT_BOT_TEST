"""
Модуль для генерации SQL запросов из естественного языка с помощью GigaChat.
"""
import os
import asyncio
import re
import logging
from typing import Optional
from gigachat import GigaChat

logger = logging.getLogger(__name__)


# Описание схемы базы данных для промпта
DATABASE_SCHEMA = """
База данных содержит информацию о видео и их статистике.

ТАБЛИЦА videos:
- id (INTEGER, PRIMARY KEY) - уникальный идентификатор видео
- creator_id (STRING) - идентификатор креатора (создателя видео)
- video_created_at (DATETIME) - дата и время публикации видео
- views_count (BIGINT) - итоговое количество просмотров
- likes_count (BIGINT) - итоговое количество лайков
- comments_count (BIGINT) - итоговое количество комментариев
- reports_count (BIGINT) - итоговое количество жалоб
- created_at (DATETIME) - дата создания записи
- updated_at (DATETIME) - дата обновления записи

ТАБЛИЦА video_snapshots:
- id (INTEGER, PRIMARY KEY) - уникальный идентификатор снапшота
- video_id (INTEGER, FOREIGN KEY -> videos.id) - ссылка на видео
- views_count (BIGINT) - количество просмотров на момент замера
- likes_count (BIGINT) - количество лайков на момент замера
- comments_count (BIGINT) - количество комментариев на момент замера
- reports_count (BIGINT) - количество жалоб на момент замера
- delta_views_count (BIGINT) - приращение просмотров с прошлого замера
- delta_likes_count (BIGINT) - приращение лайков с прошлого замера
- delta_comments_count (BIGINT) - приращение комментариев с прошлого замера
- delta_reports_count (BIGINT) - приращение жалоб с прошлого замера
- created_at (DATETIME) - время замера (снапшот делается каждый час)
- updated_at (DATETIME) - дата обновления записи

ВАЖНО:
- Для итоговой статистики используй таблицу videos
- Для динамики и прироста используй таблицу video_snapshots
- При работе с датами используй функции PostgreSQL: DATE(), DATE_TRUNC(), TO_DATE()
- Русские названия месяцев нужно преобразовать в даты: "28 ноября 2025" -> DATE '2025-11-28'
- Для диапазонов дат используй BETWEEN или >= и <=
"""

SYSTEM_PROMPT = f"""Ты - эксперт по SQL запросам для PostgreSQL. Твоя задача - преобразовать вопрос на русском языке в корректный SQL запрос.

{DATABASE_SCHEMA}

КРИТИЧЕСКИ ВАЖНО:
1. Возвращай ТОЛЬКО SQL запрос, БЕЗ ЛЮБЫХ объяснений, комментариев или дополнительного текста
2. Используй ТОЛЬКО SELECT запросы (запрещены DROP, DELETE, UPDATE, INSERT, ALTER, CREATE)
3. Запрос ДОЛЖЕН возвращать одно число (используй COUNT, SUM, MAX, MIN, AVG и т.д.)
4. НЕ добавляй никакого текста до или после SQL запроса
5. НЕ используй markdown форматирование (```sql или ```)

ОБРАБОТКА ДАТ:
- "28 ноября 2025" -> DATE '2025-11-28'
- "27 ноября" -> DATE '2025-11-27' (если год не указан, используй 2025)
- "с 1 по 5 ноября 2025 включительно" -> BETWEEN DATE '2025-11-01' AND DATE '2025-11-05'
- "с 1 ноября по 5 ноября 2025" -> BETWEEN DATE '2025-11-01' AND DATE '2025-11-05'
- "1 ноября 2025" -> DATE '2025-11-01'
- Для работы с датами используй функцию DATE() для извлечения даты из DATETIME

ПОНИМАНИЕ ВОПРОСОВ:
- "сколько" = COUNT
- "сумма", "всего", "суммарно" = SUM
- "прирост", "выросли", "увеличились" = используй delta_*_count или разницу
- "больше", "превышает" = >
- "меньше" = <
- "равно" = =
- "разные", "уникальные" = DISTINCT
- "за всё время", "всего" = без фильтра по дате
- "за дату X" = фильтр по DATE(created_at) или DATE(video_created_at)

ПРИМЕРЫ ВОПРОСОВ И SQL:

Вопрос: "Сколько всего видео есть в системе?"
SQL: SELECT COUNT(*) FROM videos;

Вопрос: "Сколько всего просмотров у всех видео?"
SQL: SELECT SUM(views_count) FROM videos;

Вопрос: "Сколько видео набрало больше 100000 просмотров за всё время?"
SQL: SELECT COUNT(*) FROM videos WHERE views_count > 100000;

Вопрос: "Сколько видео набрало больше 100 000 просмотров за всё время?"
SQL: SELECT COUNT(*) FROM videos WHERE views_count > 100000;

Вопрос: "На сколько просмотров в сумме выросли все видео 28 ноября 2025?"
SQL: SELECT SUM(delta_views_count) FROM video_snapshots WHERE DATE(created_at) = DATE '2025-11-28';

Вопрос: "Сколько разных видео получали новые просмотры 27 ноября 2025?"
SQL: SELECT COUNT(DISTINCT video_id) FROM video_snapshots WHERE DATE(created_at) = DATE '2025-11-27' AND delta_views_count > 0;

Вопрос: "Сколько видео у креатора с id creator123 вышло с 1 ноября 2025 по 5 ноября 2025 включительно?"
SQL: SELECT COUNT(*) FROM videos WHERE creator_id = 'creator123' AND DATE(video_created_at) BETWEEN DATE '2025-11-01' AND DATE '2025-11-05';

Вопрос: "Какая сумма всех лайков?"
SQL: SELECT SUM(likes_count) FROM videos;

Вопрос: "Сколько видео опубликовано 15 ноября?"
SQL: SELECT COUNT(*) FROM videos WHERE DATE(video_created_at) = DATE '2025-11-15';

Вопрос: "На сколько увеличились просмотры всех видео за 28 ноября?"
SQL: SELECT SUM(delta_views_count) FROM video_snapshots WHERE DATE(created_at) = DATE '2025-11-28';

Вопрос: "Сколько уникальных креаторов есть в базе?"
SQL: SELECT COUNT(DISTINCT creator_id) FROM videos;

Вопрос: "Какое максимальное количество просмотров у видео?"
SQL: SELECT MAX(views_count) FROM videos;

Вопрос: "Сколько лайков у всех видео вместе?"
SQL: SELECT SUM(likes_count) FROM videos;

Вопрос: "Сколько комментариев получили видео за весь период?"
SQL: SELECT SUM(comments_count) FROM videos;

Вопрос: "Сколько видео создано креатором creator456?"
SQL: SELECT COUNT(*) FROM videos WHERE creator_id = 'creator456';

Вопрос: "На сколько увеличились лайки всех видео 29 ноября 2025?"
SQL: SELECT SUM(delta_likes_count) FROM video_snapshots WHERE DATE(created_at) = DATE '2025-11-29';

Вопрос: "Какое количество видео с просмотрами более 50000?"
SQL: SELECT COUNT(*) FROM videos WHERE views_count > 50000;

Вопрос: "Сколько видео опубликовано в ноябре 2025?"
SQL: SELECT COUNT(*) FROM videos WHERE DATE(video_created_at) >= DATE '2025-11-01' AND DATE(video_created_at) <= DATE '2025-11-30';

ВАЖНО: 
- Всегда возвращай ТОЛЬКО SQL запрос
- НЕ добавляй объяснения, комментарии или дополнительный текст
- НЕ используй markdown форматирование
- Если вопрос неоднозначен, выбирай наиболее вероятную интерпретацию

Теперь преобразуй следующий вопрос в SQL запрос. Верни ТОЛЬКО SQL, без дополнительного текста:"""


class SQLQueryGenerator:
    """Генератор SQL запросов из естественного языка с помощью GigaChat."""
    
    def __init__(self, credentials: str, scope: str = "GIGACHAT_API_PERS"):
        """
        Инициализация генератора.
        
        Args:
            credentials: Authorization key (токен авторизации) GigaChat
            scope: Область действия API (GIGACHAT_API_PERS, GIGACHAT_API_B2B, GIGACHAT_API_CORP)
        """
        self.credentials = credentials
        self.scope = scope
        self._client = None
    
    def _get_client(self) -> GigaChat:
        """Получает или создает клиент GigaChat."""
        if self._client is None:
            self._client = GigaChat(
                credentials=self.credentials,
                scope=self.scope,
                verify_ssl_certs=False
            )
        return self._client
    
    def _normalize_query(self, query: str) -> str:
        """
        Нормализует вопрос пользователя для лучшего понимания.
        
        Args:
            query: Исходный вопрос
        
        Returns:
            Нормализованный вопрос
        """
        # Убираем лишние пробелы
        query = ' '.join(query.split())
        
        # Нормализуем числа с пробелами (100 000 -> 100000)
        # Ищем паттерны типа "100 000", "1 000 000" и т.д.
        query = re.sub(r'(\d+)\s+(\d+)', r'\1\2', query)
        
        # Приводим к нижнему регистру для некоторых замен
        query_lower = query.lower()
        
        # Замены для лучшего понимания
        replacements = {
            'сколько всего': 'сколько',
            'какое количество': 'сколько',
            'какая сумма': 'сколько всего',
            'суммарно': 'всего',
            'в сумме': 'всего',
            'всего вместе': 'всего',
            'за весь период': 'за всё время',
            'за все время': 'за всё время',
            'за всё время': 'за всё время',
        }
        
        for old, new in replacements.items():
            if old in query_lower:
                query = query.replace(old, new)
                query_lower = query.lower()
        
        return query.strip()
    
    async def generate_sql(self, user_query: str) -> str:
        """
        Генерирует SQL запрос из вопроса на естественном языке.
        
        Args:
            user_query: Вопрос пользователя на русском языке
        
        Returns:
            SQL запрос в виде строки
        
        Raises:
            Exception: При ошибке обращения к API или генерации запроса
        """
        try:
            # Нормализуем вопрос
            normalized_query = self._normalize_query(user_query)
            logger.info(f"Генерация SQL для вопроса: {normalized_query}")
            
            # Формируем полный промпт с четкой инструкцией
            full_prompt = f"""{SYSTEM_PROMPT}

Вопрос пользователя: {normalized_query}

Верни ТОЛЬКО SQL запрос, без объяснений:"""
            
            # Выполняем запрос в отдельном потоке, так как GigaChat синхронный
            client = self._get_client()
            
            # Используем asyncio.to_thread для выполнения синхронного кода
            response = await asyncio.to_thread(
                client.chat,
                full_prompt
            )
            
            logger.debug(f"Ответ от GigaChat: {response}")
            
            # Извлекаем текст ответа
            text = None
            if hasattr(response, 'choices') and len(response.choices) > 0:
                text = response.choices[0].message.content.strip()
            elif hasattr(response, 'content'):
                text = response.content.strip()
            elif isinstance(response, str):
                text = response.strip()
            else:
                # Пробуем получить текст из различных атрибутов
                for attr in ['text', 'message', 'result']:
                    if hasattr(response, attr):
                        value = getattr(response, attr)
                        if isinstance(value, str):
                            text = value.strip()
                            break
                        elif hasattr(value, 'content'):
                            text = value.content.strip()
                            break
                
                if not text:
                    raise Exception(f"Неожиданный формат ответа от GigaChat: {type(response)}, атрибуты: {dir(response)}")
            
            logger.debug(f"Извлеченный текст: {text[:200]}")
            
            # Очищаем ответ от markdown форматирования
            if "```sql" in text:
                # Извлекаем SQL из блока кода
                start = text.find("```sql") + 6
                end = text.find("```", start)
                if end != -1:
                    text = text[start:end].strip()
                else:
                    text = text.replace("```sql", "").replace("```", "").strip()
            elif "```" in text:
                # Убираем любые блоки кода
                text = re.sub(r'```[a-z]*\n?', '', text)
                text = text.replace("```", "").strip()
            
            # Убираем лишние пробелы и переносы строк, но сохраняем структуру SQL
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = ' '.join(lines)
            
            # Убираем возможные префиксы типа "SQL:", "Запрос:" и т.д.
            prefixes = [
                "SQL:", "sql:", "Запрос:", "запрос:", "Ответ:", "ответ:",
                "Вот SQL запрос:", "SQL запрос:", "Запрос SQL:",
                "SELECT", "select"  # На случай если есть текст перед SELECT
            ]
            for prefix in prefixes:
                if text.startswith(prefix):
                    text = text[len(prefix):].strip()
                    break
            
            # Проверяем, что это похоже на SQL запрос
            text_upper = text.upper().strip()
            if not text_upper.startswith("SELECT"):
                # Пробуем найти SELECT в тексте
                select_pos = text_upper.find("SELECT")
                if select_pos != -1:
                    text = text[select_pos:].strip()
                    # Убираем возможный текст после SQL (объяснения)
                    # Ищем конец SQL запроса по точке с запятой или ключевым словам
                    semicolon_pos = text.find(';')
                    if semicolon_pos != -1:
                        text = text[:semicolon_pos + 1]
                    else:
                        # Пробуем найти конец по ключевым словам, которые могут быть после SQL
                        end_markers = ['\n\n', 'Этот запрос', 'Запрос', 'SQL', 'SELECT']
                        for marker in end_markers:
                            if marker in text and text.find(marker) > len(text) * 0.3:
                                # Если маркер найден далеко от начала, обрезаем
                                marker_pos = text.find(marker, len(text) // 2)
                                if marker_pos != -1:
                                    text = text[:marker_pos].strip()
                                    break
                else:
                    logger.error(f"Ответ не содержит SQL запрос: {text[:200]}")
                    raise Exception(f"Ответ не содержит SQL запрос. Получено: {text[:100]}...")
            
            # Убираем точку с запятой в конце (она не обязательна для выполнения)
            text = text.rstrip(';').strip()
            
            # Финальная проверка
            if not text or len(text) < 10:
                raise Exception("Пустой или слишком короткий ответ от GigaChat")
            
            if not text.upper().startswith("SELECT"):
                raise Exception(f"Ответ не начинается с SELECT: {text[:50]}")
            
            logger.info(f"Сгенерированный SQL: {text}")
            return text
            
        except Exception as e:
            raise Exception(f"Ошибка при обращении к GigaChat API: {e}")


def create_generator() -> Optional[SQLQueryGenerator]:
    """
    Создает генератор SQL запросов из переменных окружения.
    
    Returns:
        SQLQueryGenerator или None, если переменные окружения не настроены
    """
    credentials = os.getenv("GIGACHAT_CREDENTIALS")
    scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    
    if not credentials:
        return None
    
    return SQLQueryGenerator(credentials, scope)
