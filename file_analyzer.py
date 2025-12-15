"""
Модуль для анализа загруженных JSON файлов и ответов на вопросы через GigaChat.
"""
import json
import asyncio
import re
import os
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger
from gigachat import GigaChat

# Путь к папке кэша
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_METADATA_FILE = CACHE_DIR / "metadata.json"


class FileAnalyzer:
    """Класс для анализа JSON файлов и ответов на вопросы через GigaChat."""

    def __init__(self, gigachat_credentials: str, gigachat_scope: str = "GIGACHAT_API_PERS"):
        """
        Инициализация анализатора файлов.

        Args:
            gigachat_credentials: Authorization key GigaChat
            gigachat_scope: Scope GigaChat API
        """
        self.credentials = gigachat_credentials
        self.scope = gigachat_scope
        self._client = None
        self.current_data: Optional[Dict[str, Any]] = None
        self.cached_file_path: Optional[str] = None
        self.cached_file_name: Optional[str] = None

        # Создаем папку кэша, если её нет
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(
                "Не удалось создать папку кэша",
                cache_dir=str(CACHE_DIR),
                error=str(e),
                error_type=type(e).__name__
            )

    def _get_client(self) -> GigaChat:
        """Получает или создает клиент GigaChat."""
        if self._client is None:
            self._client = GigaChat(
                credentials=self.credentials,
                scope=self.scope,
                verify_ssl_certs=False
            )
        return self._client

    def _calculate_file_hash(self, file_path: str) -> str:
        """
        Вычисляет хеш файла для проверки изменений.

        Args:
            file_path: Путь к файлу

        Returns:
            SHA256 хеш файла
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _save_to_cache(self, source_file_path: str, file_name: str) -> str:
        """
        Сохраняет файл в кэш и обновляет метаданные.

        Args:
            source_file_path: Путь к исходному файлу
            file_name: Имя файла для сохранения

        Returns:
            Путь к сохраненному файлу в кэше

        Raises:
            Exception: Если не удалось сохранить файл в кэш
        """
        try:
            # Убеждаемся, что папка кэша существует
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

            # Вычисляем хеш файла
            file_hash = self._calculate_file_hash(source_file_path)

            # Очищаем имя файла от недопустимых символов
            safe_file_name = "".join(
                c for c in file_name if c.isalnum() or c in "._-"
            ) or "file.json"

            # Создаем имя файла в кэше на основе хеша
            cache_file_name = f"{file_hash[:16]}_{safe_file_name}"
            cache_file_path = CACHE_DIR / cache_file_name

            # Копируем файл в кэш
            shutil.copy2(source_file_path, cache_file_path)

            # Сохраняем метаданные
            metadata = {
                'file_name': file_name,
                'cache_file_name': cache_file_name,
                'file_hash': file_hash,
                'cached_at': datetime.now().isoformat(),
                'file_path': str(cache_file_path)
            }

            with open(CACHE_METADATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            logger.info(
                "Файл сохранен в кэш",
                cache_file=str(cache_file_path),
                source_file=source_file_path,
                file_name=file_name,
                file_hash=file_hash[:16]
            )
            return str(cache_file_path)
        except Exception as e:
            logger.exception(
                "Ошибка при сохранении в кэш",
                source_file=source_file_path,
                file_name=file_name,
                cache_dir=str(CACHE_DIR),
                error=str(e),
                error_type=type(e).__name__
            )
            raise Exception(f"Не удалось сохранить файл в кэш: {e}")

    def _load_from_cache(self) -> Optional[str]:
        """
        Загружает файл из кэша, если он существует.

        Returns:
            Путь к файлу в кэше или None, если кэш пуст
        """
        if not CACHE_METADATA_FILE.exists():
            return None

        try:
            with open(CACHE_METADATA_FILE, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            cache_file_path = metadata.get('file_path')
            if cache_file_path and os.path.exists(cache_file_path):
                self.cached_file_name = metadata.get('file_name', 'cached_file.json')
                logger.info(
                    "Загружен файл из кэша",
                    cache_file=cache_file_path,
                    file_name=self.cached_file_name,
                    cached_at=metadata.get('cached_at')
                )
                return cache_file_path
            else:
                logger.warning(
                    "Файл в кэше не найден, очищаю метаданные",
                    expected_file=cache_file_path
                )
                self._clear_cache()
                return None
        except Exception as e:
            logger.warning(
                "Ошибка при загрузке из кэша",
                metadata_file=str(CACHE_METADATA_FILE),
                error=str(e),
                error_type=type(e).__name__
            )
            return None

    def _clear_cache(self):
        """Очищает кэш и метаданные."""
        if CACHE_METADATA_FILE.exists():
            try:
                metadata = json.load(open(CACHE_METADATA_FILE, 'r', encoding='utf-8'))
                cache_file_path = metadata.get('file_path')
                if cache_file_path and os.path.exists(cache_file_path):
                    os.unlink(cache_file_path)
            except Exception as e:
                logger.warning(
                    "Ошибка при удалении файла из кэша",
                    cache_file=cache_file_path,
                    error=str(e),
                    error_type=type(e).__name__
                )

            try:
                os.unlink(CACHE_METADATA_FILE)
            except Exception as e:
                logger.warning(
                    "Ошибка при удалении метаданных",
                    metadata_file=str(CACHE_METADATA_FILE),
                    error=str(e),
                    error_type=type(e).__name__
                )

        self.cached_file_path = None
        self.cached_file_name = None

    def load_json_file(self, file_path: str, cache: bool = True) -> Dict[str, Any]:
        """
        Загружает JSON файл.

        Args:
            file_path: Путь к JSON файлу
            cache: Сохранять ли файл в кэш (по умолчанию True)

        Returns:
            Словарь с данными из файла
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.current_data = data

            # Сохраняем в кэш, если указано
            if cache:
                try:
                    file_name = os.path.basename(file_path)
                    self.cached_file_path = self._save_to_cache(file_path, file_name)
                    self.cached_file_name = file_name
                    logger.info(
                        "Файл сохранен в кэш",
                        cache_file=self.cached_file_path,
                        source_file=file_path
                    )
                except Exception as cache_error:
                    # Если не удалось сохранить в кэш, продолжаем без кэширования
                    logger.warning(
                        "Не удалось сохранить файл в кэш, файл загружен без кэширования",
                        file_path=file_path,
                        error=str(cache_error),
                        error_type=type(cache_error).__name__
                    )

            logger.info(
                "Файл успешно загружен",
                file_path=file_path,
                cached=(self.cached_file_path is not None),
                file_size=os.path.getsize(file_path) if os.path.exists(file_path) else None
            )
            return data
        except json.JSONDecodeError as e:
            logger.error(
                "Ошибка парсинга JSON",
                file_path=file_path,
                error=str(e),
                error_line=getattr(e, 'lineno', None),
                error_column=getattr(e, 'colno', None)
            )
            raise ValueError(f"Ошибка парсинга JSON: {e}")
        except FileNotFoundError:
            logger.error(
                "Файл не найден",
                file_path=file_path
            )
            raise FileNotFoundError(f"Файл {file_path} не найден")
        except Exception as e:
            logger.exception(
                "Ошибка при загрузке файла",
                file_path=file_path,
                error=str(e),
                error_type=type(e).__name__
            )
            raise Exception(f"Ошибка при загрузке файла: {e}")

    def _summarize_data(self, data: Dict[str, Any]) -> str:
        """
        Создает краткое описание структуры данных для промпта.

        Args:
            data: Данные из JSON файла

        Returns:
            Текстовое описание структуры данных
        """
        summary_parts = []

        if isinstance(data, dict):
            # Анализируем структуру
            if 'videos' in data and isinstance(data['videos'], list):
                videos_count = len(data['videos'])
                summary_parts.append(f"Файл содержит {videos_count} видео.")

                if videos_count > 0:
                    first_video = data['videos'][0]
                    summary_parts.append("\nСтруктура данных о видео:")
                    summary_parts.append(f"- id: {first_video.get('id', 'N/A')}")
                    summary_parts.append(f"- creator_id: {first_video.get('creator_id', 'N/A')}")
                    summary_parts.append(f"- video_created_at: {first_video.get('video_created_at', 'N/A')}")
                    summary_parts.append(f"- views_count: {first_video.get('views_count', 'N/A')}")
                    summary_parts.append(f"- likes_count: {first_video.get('likes_count', 'N/A')}")
                    summary_parts.append(f"- comments_count: {first_video.get('comments_count', 'N/A')}")
                    summary_parts.append(f"- reports_count: {first_video.get('reports_count', 'N/A')}")

                    # Проверяем наличие snapshots
                    if 'snapshots' in first_video and isinstance(first_video['snapshots'], list):
                        snapshots_count = len(first_video['snapshots'])
                        summary_parts.append(f"\nУ первого видео {snapshots_count} снапшотов.")
                        if snapshots_count > 0:
                            first_snapshot = first_video['snapshots'][0]
                            summary_parts.append("\nСтруктура снапшотов:")
                            summary_parts.append(f"- id: {first_snapshot.get('id', 'N/A')}")
                            summary_parts.append(f"- video_id: {first_snapshot.get('video_id', 'N/A')}")
                            summary_parts.append(f"- views_count: {first_snapshot.get('views_count', 'N/A')}")
                            summary_parts.append(f"- likes_count: {first_snapshot.get('likes_count', 'N/A')}")
                            summary_parts.append(f"- delta_views_count: {first_snapshot.get('delta_views_count', 'N/A')}")
                            summary_parts.append(f"- delta_likes_count: {first_snapshot.get('delta_likes_count', 'N/A')}")
                            summary_parts.append(f"- created_at: {first_snapshot.get('created_at', 'N/A')}")

            # Добавляем статистику
            summary_parts.append("\nОбщая статистика:")
            if 'videos' in data and isinstance(data['videos'], list):
                total_views = sum(v.get('views_count', 0) for v in data['videos'])
                total_likes = sum(v.get('likes_count', 0) for v in data['videos'])
                total_comments = sum(v.get('comments_count', 0) for v in data['videos'])
                summary_parts.append(f"- Всего видео: {len(data['videos'])}")
                summary_parts.append(f"- Сумма просмотров: {total_views}")
                summary_parts.append(f"- Сумма лайков: {total_likes}")
                summary_parts.append(f"- Сумма комментариев: {total_comments}")

        return "\n".join(summary_parts)

    def _extract_number(self, text: str) -> str:
        """
        Извлекает число из текста ответа.

        Args:
            text: Текст ответа от GigaChat

        Returns:
            Число в виде строки без пробелов и символов форматирования
        """
        # Убираем LaTeX-форматирование ($$ ... $$)
        text = re.sub(r'\$\$.*?\$\$', '', text, flags=re.DOTALL)
        text = re.sub(r'\$[^$]*?\$', '', text)

        # Убираем markdown-форматирование для кода
        text = re.sub(r'```[a-z]*\n?', '', text)
        text = text.replace('```', '')

        # Убираем markdown жирный текст (**текст**)
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)

        # Ищем число в тексте (может быть с пробелами как разделителями тысяч)
        # Паттерн: последовательность цифр, возможно разделенных пробелами
        # Примеры: "3 326 609", "3326609", "150", "85 234"
        number_pattern = r'[\d\s]+'
        matches = re.findall(number_pattern, text)

        if matches:
            # Берем самое длинное совпадение (скорее всего это искомое число)
            longest_match = max(matches, key=lambda x: len(re.sub(r'\s', '', x)))
            # Убираем все пробелы из числа
            number = re.sub(r'\s', '', longest_match)
            # Проверяем, что это действительно число
            if number.isdigit():
                return number

        # Если не нашли число, пробуем найти любое число (включая десятичные)
        decimal_pattern = r'\d+[.,]?\d*'
        decimal_matches = re.findall(decimal_pattern, text)

        if decimal_matches:
            # Берем первое найденное число
            number_str = decimal_matches[0].replace(',', '.').replace(' ', '')
            # Если это целое число, возвращаем без десятичной части
            try:
                num = float(number_str)
                if num == int(num):
                    return str(int(num))
                return str(int(num))  # Все равно возвращаем целое число
            except ValueError:
                pass

        # Если ничего не найдено, возвращаем 0
        return "0"

    def _clean_response(self, text: str) -> str:
        """
        Очищает ответ от лишних символов форматирования.

        Args:
            text: Исходный текст ответа

        Returns:
            Очищенный текст
        """
        # Убираем LaTeX-форматирование ($$ ... $$)
        text = re.sub(r'\$\$.*?\$\$', '', text, flags=re.DOTALL)
        text = re.sub(r'\$[^$]*?\$', '', text)

        # Убираем markdown-форматирование для кода
        text = re.sub(r'```[a-z]*\n?', '', text)
        text = text.replace('```', '')

        # Убираем лишние переносы строк (более 2 подряд)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Убираем лишние пробелы (но сохраняем один пробел между словами)
        text = re.sub(r'[ \t]+', ' ', text)

        # Убираем пробелы в начале и конце строк
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)

        # Убираем пустые строки в начале и конце
        text = text.strip()

        return text

    def _prepare_data_context(self, data: Dict[str, Any], max_size: int = 50000) -> str:
        """
        Подготавливает контекст данных для промпта.
        Если данные слишком большие, создает сводку.

        Args:
            data: Данные из JSON файла
            max_size: Максимальный размер контекста в символах

        Returns:
            Текстовое представление данных
        """
        # Преобразуем данные в JSON строку
        json_str = json.dumps(data, ensure_ascii=False, indent=2)

        # Если данные слишком большие, создаем сводку
        if len(json_str) > max_size:
            logger.info(
                "Данные слишком большие, создаю сводку",
                data_size=len(json_str),
                max_size=max_size,
                reduction_percent=round((1 - max_size / len(json_str)) * 100, 1)
            )
            summary = self._summarize_data(data)

            # Добавляем примеры данных
            if isinstance(data, dict) and 'videos' in data and isinstance(data['videos'], list):
                # Берем первые 3 видео как примеры
                sample_data = {
                    'videos': data['videos'][:3]
                }
                sample_json = json.dumps(sample_data, ensure_ascii=False, indent=2)
                return f"{summary}\n\nПримеры данных (первые 3 видео):\n{sample_json}"

            return summary

        return json_str

    async def answer_question(self, question: str) -> str:
        """
        Отвечает на вопрос пользователя на основе загруженных данных.

        Args:
            question: Вопрос пользователя на русском языке

        Returns:
            Ответ на вопрос
        """
        if self.current_data is None:
            raise ValueError("Данные не загружены. Сначала загрузите JSON файл.")

        try:
            # Подготавливаем контекст данных
            data_context = self._prepare_data_context(self.current_data)

            # Формируем промпт для GigaChat
            system_prompt = """Ты - помощник для анализа данных о видео и их статистике.
Твоя задача - отвечать на вопросы пользователя на основе предоставленных данных.

КРИТИЧЕСКИ ВАЖНО:
1. Возвращай ТОЛЬКО число без текста, пробелов и символов форматирования
2. Если вопрос требует подсчета, верни только результат вычисления
3. Используй точные значения из данных
4. НЕ добавляй никаких объяснений, текста или единиц измерения
5. НЕ используй пробелы в числе (например: 3326609, а не 3 326 609)
6. НЕ используй markdown форматирование (**текст**, ```код``` и т.д.)
7. НЕ используй LaTeX-форматирование ($$, формулы и т.д.)
8. Если данных недостаточно для ответа, верни 0

ПРИМЕРЫ:
Вопрос: "Сколько всего просмотров у всех видео?"
Ответ: 3326609

Вопрос: "Сколько видео в файле?"
Ответ: 150

Вопрос: "Какое общее количество лайков?"
Ответ: 85234

Структура данных:
- videos: массив объектов с информацией о видео
  - id: идентификатор видео
  - creator_id: идентификатор креатора
  - video_created_at: дата создания видео
  - views_count: количество просмотров
  - likes_count: количество лайков
  - comments_count: количество комментариев
  - reports_count: количество жалоб
  - snapshots: массив снапшотов (почасовых замеров статистики)
    - views_count, likes_count, comments_count, reports_count: текущие значения
    - delta_views_count, delta_likes_count, etc.: приращения с предыдущего замера
    - created_at: время замера

Верни ТОЛЬКО число без текста:"""

            user_prompt = f"""Данные:

{data_context}

Вопрос пользователя: {question}

Верни ТОЛЬКО число без текста, пробелов и символов форматирования."""

            # Выполняем запрос к GigaChat
            client = self._get_client()

            full_prompt = f"{system_prompt}\n\n{user_prompt}"

            # Используем asyncio.to_thread для выполнения синхронного кода
            response = await asyncio.to_thread(
                client.chat,
                full_prompt
            )

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
                    raise Exception(f"Неожиданный формат ответа от GigaChat: {type(response)}")

            logger.info(
                "Ответ от GigaChat получен",
                question=question[:100] + "..." if len(question) > 100 else question,
                response_preview=text[:100] + "..." if len(text) > 100 else text,
                response_length=len(text)
            )

            # Извлекаем число из ответа
            number = self._extract_number(text)

            logger.debug(
                "Число извлечено из ответа",
                extracted_number=number,
                original_response=text[:200]
            )

            return number

        except Exception as e:
            logger.exception(
                "Ошибка при обработке вопроса",
                question=question[:200] if len(question) > 200 else question,
                has_data=(self.current_data is not None),
                error=str(e),
                error_type=type(e).__name__
            )
            raise Exception(f"Ошибка при обработке вопроса: {e}")

    def has_data(self) -> bool:
        """Проверяет, загружены ли данные."""
        return self.current_data is not None

    def clear_data(self):
        """Очищает загруженные данные и кэш."""
        self.current_data = None
        self._clear_cache()
        logger.info(
            "Данные и кэш очищены",
            had_cached_file=(self.cached_file_path is not None),
            cached_file_name=self.cached_file_name
        )

    def load_cached_file(self) -> bool:
        """
        Загружает файл из кэша, если он существует.

        Returns:
            True если файл был загружен, False иначе
        """
        cache_file_path = self._load_from_cache()
        if cache_file_path:
            try:
                self.load_json_file(cache_file_path, cache=False)
                self.cached_file_path = cache_file_path
                return True
            except Exception as e:
                logger.exception(
                    "Ошибка при загрузке файла из кэша",
                    cache_file_path=cache_file_path,
                    error=str(e),
                    error_type=type(e).__name__
                )
                self._clear_cache()
                return False
        return False

    def get_cached_file_info(self) -> Optional[Dict[str, Any]]:
        """
        Возвращает информацию о закэшированном файле.

        Returns:
            Словарь с информацией о файле или None
        """
        if not CACHE_METADATA_FILE.exists():
            return None

        try:
            with open(CACHE_METADATA_FILE, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            cache_file_path = metadata.get('file_path')
            if cache_file_path and os.path.exists(cache_file_path):
                return metadata
            return None
        except Exception as e:
            logger.warning(
                "Ошибка при чтении метаданных",
                metadata_file=str(CACHE_METADATA_FILE),
                error=str(e),
                error_type=type(e).__name__
            )
            return None
