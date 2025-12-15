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
from typing import Optional, Dict, Any, Tuple
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

    def _validate_data_structure(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Валидирует структуру данных JSON.

        Args:
            data: Данные из JSON файла

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
            - is_valid: True если структура валидна, False иначе
            - error_message: Сообщение об ошибке или None если валидация прошла успешно
        """
        # Проверяем, что данные - это словарь
        if not isinstance(data, dict):
            return False, "Данные должны быть объектом (словарем), а не массивом или примитивом"

        # Проверяем наличие ключа 'videos'
        if 'videos' not in data:
            return False, "Отсутствует ключ 'videos' в корневом объекте данных"

        # Проверяем, что 'videos' - это список
        videos = data.get('videos')
        if not isinstance(videos, list):
            return False, "Поле 'videos' должно быть массивом"

        # Проверяем, что массив не пустой
        if len(videos) == 0:
            return False, "Массив 'videos' пуст"

        # UUID паттерн: 8-4-4-4-12 шестнадцатеричных символов
        uuid_pattern = re.compile(
            r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        )

        # Валидируем каждое видео
        for idx, video in enumerate(videos):
            if not isinstance(video, dict):
                return False, f"Видео #{idx + 1} должно быть объектом, а не {type(video).__name__}"

            # Проверяем обязательные поля
            if 'id' not in video:
                return False, f"Видео #{idx + 1} не содержит обязательное поле 'id'"

            video_id = video.get('id')
            # Проверяем формат UUID
            if not isinstance(video_id, str):
                return False, f"Поле 'id' видео #{idx + 1} должно быть строкой, получен {type(video_id).__name__}"

            if not uuid_pattern.match(video_id):
                return False, (
                    f"Поле 'id' видео #{idx + 1} не соответствует формату UUID. "
                    f"Ожидается формат: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx, "
                    f"получено: {video_id[:50]}"
                )

            if 'creator_id' not in video:
                return False, f"Видео #{idx + 1} не содержит обязательное поле 'creator_id'"

            # Валидируем снапшоты, если они есть
            if 'snapshots' in video:
                snapshots = video.get('snapshots')
                if not isinstance(snapshots, list):
                    return False, f"Поле 'snapshots' видео #{idx + 1} должно быть массивом"

                for snap_idx, snapshot in enumerate(snapshots):
                    if not isinstance(snapshot, dict):
                        return False, (
                            f"Снапшот #{snap_idx + 1} видео #{idx + 1} должен быть объектом, "
                            f"а не {type(snapshot).__name__}"
                        )

                    if 'video_id' not in snapshot:
                        return False, (
                            f"Снапшот #{snap_idx + 1} видео #{idx + 1} не содержит "
                            f"обязательное поле 'video_id'"
                        )

                    snapshot_video_id = snapshot.get('video_id')
                    # Проверяем, что video_id снапшота совпадает с id видео
                    if snapshot_video_id != video_id:
                        return False, (
                            f"Снапшот #{snap_idx + 1} видео #{idx + 1} имеет несоответствующий "
                            f"video_id: ожидается '{video_id}', получено '{snapshot_video_id}'"
                        )

                    if 'created_at' not in snapshot:
                        return False, (
                            f"Снапшот #{snap_idx + 1} видео #{idx + 1} не содержит "
                            f"обязательное поле 'created_at'"
                        )

        return True, None

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

            # Валидируем структуру данных
            is_valid, error_message = self._validate_data_structure(data)
            if not is_valid:
                logger.error(
                    "Ошибка валидации структуры данных",
                    file_path=file_path,
                    error=error_message
                )
                raise ValueError(f"Неверная структура данных: {error_message}")

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
            error_msg = (
                f"Ошибка парсинга JSON в файле '{file_path}': {str(e)}. "
                f"Проверьте синтаксис JSON файла."
            )
            if hasattr(e, 'lineno') and e.lineno:
                error_msg += f" Ошибка на строке {e.lineno}"
            if hasattr(e, 'colno') and e.colno:
                error_msg += f", столбец {e.colno}"
            logger.error(
                "Ошибка парсинга JSON",
                file_path=file_path,
                error=str(e),
                error_line=getattr(e, 'lineno', None),
                error_column=getattr(e, 'colno', None)
            )
            raise ValueError(error_msg)
        except FileNotFoundError:
            error_msg = (
                f"Файл '{file_path}' не найден. "
                f"Убедитесь, что путь к файлу указан правильно и файл существует."
            )
            logger.error(
                "Файл не найден",
                file_path=file_path
            )
            raise FileNotFoundError(error_msg)
        except ValueError as e:
            # Перехватываем ValueError от валидации и пробрасываем дальше
            logger.error(
                "Ошибка валидации данных",
                file_path=file_path,
                error=str(e)
            )
            raise
        except Exception as e:
            error_msg = (
                f"Неожиданная ошибка при загрузке файла '{file_path}': {str(e)}. "
                f"Тип ошибки: {type(e).__name__}"
            )
            logger.exception(
                "Ошибка при загрузке файла",
                file_path=file_path,
                error=str(e),
                error_type=type(e).__name__
            )
            raise Exception(error_msg) from e

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
                    first_video_id = first_video.get('id', 'N/A')
                    summary_parts.append("\nСтруктура данных о видео:")
                    summary_parts.append(f"- id: {first_video_id} (UUID формат: строка из 32 шестнадцатеричных символов)")
                    summary_parts.append(f"- creator_id: {first_video.get('creator_id', 'N/A')}")
                    summary_parts.append(f"- video_created_at: {first_video.get('video_created_at', 'N/A')}")
                    summary_parts.append(f"- views_count: {first_video.get('views_count', 'N/A')}")
                    summary_parts.append(f"- likes_count: {first_video.get('likes_count', 'N/A')}")
                    summary_parts.append(f"- comments_count: {first_video.get('comments_count', 'N/A')}")
                    summary_parts.append(f"- reports_count: {first_video.get('reports_count', 'N/A')}")
                    if 'created_at' in first_video:
                        summary_parts.append(f"- created_at: {first_video.get('created_at', 'N/A')} (дата создания записи)")
                    if 'updated_at' in first_video:
                        summary_parts.append(f"- updated_at: {first_video.get('updated_at', 'N/A')} (дата обновления записи)")

                    # Проверяем формат UUID
                    uuid_pattern = re.compile(
                        r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
                    )
                    if isinstance(first_video_id, str) and uuid_pattern.match(first_video_id):
                        summary_parts.append("  ✓ ID соответствует формату UUID")
                    elif isinstance(first_video_id, str):
                        summary_parts.append(
                            "  ⚠ ID не соответствует стандартному формату UUID"
                        )

                    # Проверяем наличие snapshots
                    if 'snapshots' in first_video and isinstance(first_video['snapshots'], list):
                        snapshots_count = len(first_video['snapshots'])
                        summary_parts.append(f"\nУ первого видео {snapshots_count} снапшотов.")
                        if snapshots_count > 0:
                            first_snapshot = first_video['snapshots'][0]
                            summary_parts.append("\nСтруктура снапшотов:")
                            summary_parts.append(f"- id: {first_snapshot.get('id', 'N/A')}")
                            snapshot_video_id = first_snapshot.get('video_id', 'N/A')
                            summary_parts.append(f"- video_id: {snapshot_video_id} (UUID, должен совпадать с id видео)")
                            summary_parts.append(f"- views_count: {first_snapshot.get('views_count', 'N/A')}")
                            summary_parts.append(f"- likes_count: {first_snapshot.get('likes_count', 'N/A')}")
                            summary_parts.append(f"- comments_count: {first_snapshot.get('comments_count', 'N/A')}")
                            summary_parts.append(f"- reports_count: {first_snapshot.get('reports_count', 'N/A')}")
                            summary_parts.append(f"- delta_views_count: {first_snapshot.get('delta_views_count', 'N/A')} (приращение просмотров)")
                            summary_parts.append(f"- delta_likes_count: {first_snapshot.get('delta_likes_count', 'N/A')} (приращение лайков)")
                            summary_parts.append(f"- delta_comments_count: {first_snapshot.get('delta_comments_count', 'N/A')} (приращение комментариев)")
                            summary_parts.append(f"- delta_reports_count: {first_snapshot.get('delta_reports_count', 'N/A')} (приращение жалоб)")
                            summary_parts.append(f"- created_at: {first_snapshot.get('created_at', 'N/A')} (время создания снапшота)")
                            summary_parts.append(f"- updated_at: {first_snapshot.get('updated_at', 'N/A')} (время обновления снапшота)")

            # Добавляем статистику
            summary_parts.append("\nОбщая статистика:")
            if 'videos' in data and isinstance(data['videos'], list):
                videos_list = data['videos']
                total_views = sum(v.get('views_count', 0) for v in videos_list)
                total_likes = sum(v.get('likes_count', 0) for v in videos_list)
                total_comments = sum(v.get('comments_count', 0) for v in videos_list)
                total_reports = sum(v.get('reports_count', 0) for v in videos_list)

                # Статистика по снапшотам
                total_snapshots = 0
                videos_with_snapshots = 0
                for v in videos_list:
                    if 'snapshots' in v and isinstance(v.get('snapshots'), list):
                        snapshots = v.get('snapshots', [])
                        total_snapshots += len(snapshots)
                        if len(snapshots) > 0:
                            videos_with_snapshots += 1

                # Статистика по UUID формату
                uuid_pattern = re.compile(
                    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
                )
                valid_uuids = sum(
                    1 for v in videos_list
                    if isinstance(v.get('id'), str) and uuid_pattern.match(v.get('id', ''))
                )

                summary_parts.append(f"- Всего видео: {len(videos_list)}")
                summary_parts.append(f"- Видео с валидным UUID: {valid_uuids}/{len(videos_list)}")
                summary_parts.append(f"- Сумма просмотров: {total_views:,}".replace(',', ' '))
                summary_parts.append(f"- Сумма лайков: {total_likes:,}".replace(',', ' '))
                summary_parts.append(f"- Сумма комментариев: {total_comments:,}".replace(',', ' '))
                summary_parts.append(f"- Сумма жалоб: {total_reports:,}".replace(',', ' '))
                summary_parts.append(f"- Всего снапшотов: {total_snapshots}")
                summary_parts.append(f"- Видео со снапшотами: {videos_with_snapshots}/{len(videos_list)}")
                if videos_with_snapshots > 0:
                    avg_snapshots = total_snapshots / videos_with_snapshots
                    summary_parts.append(f"- Среднее количество снапшотов на видео: {avg_snapshots:.1f}")

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

    def _prepare_data_context(self, data: Dict[str, Any], max_size: int = 100000) -> str:
        """
        Подготавливает контекст данных для промпта.
        Если данные слишком большие, создает сводку с умной выборкой примеров.

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

            # Добавляем примеры данных с умной выборкой
            if isinstance(data, dict) and 'videos' in data and isinstance(data['videos'], list):
                videos = data['videos']
                sample_videos = self._select_sample_videos(videos, max_samples=3)

                sample_data = {
                    'videos': sample_videos
                }
                sample_json = json.dumps(sample_data, ensure_ascii=False, indent=2)
                return f"{summary}\n\nПримеры данных (выбрано {len(sample_videos)} репрезентативных видео):\n{sample_json}"

            return summary

        return json_str

    def _select_sample_videos(self, videos: list, max_samples: int = 3) -> list:
        """
        Выбирает репрезентативные примеры видео для контекста.

        Стратегия выборки:
        1. Первое видео (для базовой структуры)
        2. Видео с наибольшим количеством снапшотов (для демонстрации полной структуры)
        3. Видео с разными характеристиками (разные даты, разные значения статистики)

        Args:
            videos: Список видео
            max_samples: Максимальное количество примеров

        Returns:
            Список выбранных видео
        """
        if len(videos) <= max_samples:
            return videos

        selected = []

        # 1. Всегда берем первое видео
        if len(videos) > 0:
            selected.append(videos[0])

        # 2. Находим видео с наибольшим количеством снапшотов
        if len(selected) < max_samples:
            videos_with_snapshots = [
                (idx, v) for idx, v in enumerate(videos)
                if idx != 0 and 'snapshots' in v and isinstance(v.get('snapshots'), list)
            ]
            if videos_with_snapshots:
                videos_with_snapshots.sort(
                    key=lambda x: len(x[1].get('snapshots', [])),
                    reverse=True
                )
                best_snapshot_video = videos_with_snapshots[0][1]
                if best_snapshot_video not in selected:
                    selected.append(best_snapshot_video)

        # 3. Берем видео с разными датами создания (если есть)
        if len(selected) < max_samples:
            # Группируем по датам создания
            videos_by_date = {}
            for v in videos:
                if v not in selected and 'video_created_at' in v:
                    date_key = v.get('video_created_at', '')[:10]  # Берем только дату
                    if date_key not in videos_by_date:
                        videos_by_date[date_key] = []
                    videos_by_date[date_key].append(v)

            # Берем по одному видео с разных дат
            for date_key, date_videos in videos_by_date.items():
                if len(selected) >= max_samples:
                    break
                if date_videos:
                    selected.append(date_videos[0])

        # 4. Если все еще не хватает, берем видео с разными значениями статистики
        if len(selected) < max_samples:
            # Сортируем по views_count и берем из разных частей списка
            sorted_by_views = sorted(
                [v for v in videos if v not in selected],
                key=lambda x: x.get('views_count', 0)
            )
            if sorted_by_views:
                # Берем из начала, середины и конца
                indices = [0, len(sorted_by_views) // 2, len(sorted_by_views) - 1]
                for idx in indices:
                    if len(selected) >= max_samples:
                        break
                    if 0 <= idx < len(sorted_by_views):
                        selected.append(sorted_by_views[idx])

        # 5. Если все еще не хватает, просто дополняем первыми доступными
        if len(selected) < max_samples:
            for v in videos:
                if len(selected) >= max_samples:
                    break
                if v not in selected:
                    selected.append(v)

        return selected[:max_samples]

    async def answer_question(self, question: str) -> str:
        """
        Отвечает на вопрос пользователя на основе загруженных данных.

        Args:
            question: Вопрос пользователя на русском языке

        Returns:
            Ответ на вопрос
        """
        if self.current_data is None:
            raise ValueError(
                "Данные не загружены. Сначала загрузите JSON файл используя метод load_json_file()."
            )

        try:
            # Подготавливаем контекст данных
            data_context = self._prepare_data_context(self.current_data)

            # Формируем промпт для GigaChat
            system_prompt = """Ты - помощник для анализа данных о видео и их статистике.
Твоя задача - отвечать на ЛЮБЫЕ вопросы пользователя на русском языке на основе предоставленных данных.

КРИТИЧЕСКИ ВАЖНО:
1. Возвращай ТОЛЬКО число без текста, пробелов и символов форматирования
2. Если вопрос требует подсчета, верни только результат вычисления
3. Используй ТОЧНЫЕ значения из данных - найди нужное видео/данные в массиве videos
4. НЕ добавляй никаких объяснений, текста или единиц измерения
5. НЕ используй пробелы в числе (например: 3326609, а не 3 326 609)
6. НЕ используй markdown форматирование (**текст**, ```код``` и т.д.)
7. НЕ используй LaTeX-форматирование ($$, формулы и т.д.)
8. Если данных недостаточно для ответа, верни 0

ВАЖНО ДЛЯ UUID:
- ID видео представлены в формате UUID (универсальный уникальный идентификатор)
- Формат UUID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (32 шестнадцатеричных символа, разделенных дефисами)
- Пример UUID: ecd8a4e4-1f24-4b97-a944-35d17078ce7c
- При поиске видео по ID сравнивай UUID ТОЧНО, учитывая ВСЕ символы и регистр
- UUID чувствителен к регистру: "ECD8A4E4" ≠ "ecd8a4e4"
- При сравнении UUID используй точное совпадение строки, символ за символом
- Если в вопросе указан UUID, найди видео где поле "id" точно совпадает с этим UUID

ПОИСК КОНКРЕТНЫХ ВИДЕО:
- Если вопрос содержит ID видео (например: "ecd8a4e4-1f24-4b97-a944-35d17078ce7c"), найди это видео в массиве videos по полю "id"
- Вопросы типа "Какая статистика по видео с id X?" означают: найди видео с id=X и верни запрошенное значение (views_count, likes_count и т.д.)
- Вопросы типа "Сколько просмотров у видео с id X?" = найди видео с id=X, верни его views_count
- Вопросы типа "Сколько лайков у видео X?" = найди видео с id=X, верни его likes_count
- Если видео с указанным UUID не найдено, верни 0

ПОНИМАНИЕ ВОПРОСОВ:

ВОПРОСЫ ПРО КОНКРЕТНОЕ ВИДЕО:
- "Какая статистика по видео с id X?" = найди видео с id=X, верни views_count (или уточни что именно спрашивают)
- "Сколько просмотров у видео с id X?" = найди видео с id=X, верни views_count
- "Сколько лайков у видео X?" = найди видео с id=X, верни likes_count
- "Какое количество комментариев у видео с id X?" = найди видео с id=X, верни comments_count
- "Сколько просмотров у видео ecd8a4e4-1f24-4b97-a944-35d17078ce7c?" = найди это видео, верни views_count
- "Статистика видео X" = найди видео с id=X, верни views_count (или уточни что именно)

ПОДСЧЕТ КОЛИЧЕСТВА:
- "сколько", "какое количество", "число", "количество" = COUNT

СУММИРОВАНИЕ:
- "сумма", "всего", "суммарно", "в сумме", "всего вместе" = SUM

МАКСИМУМ/МИНИМУМ:
- "максимальное", "максимум", "наибольшее" = MAX
- "минимальное", "минимум", "наименьшее" = MIN

ПОЛЯ ДАННЫХ (понимай синонимы):
- "просмотры", "просмотров", "views", "статистика" (если не уточнено) = views_count
- "лайки", "лайков", "likes" = likes_count
- "комментарии", "комментариев", "comments" = comments_count
- "репосты", "репостов", "reports" = reports_count

ОБРАБОТКА ДАТ:

ПОНИМАНИЕ ДАТ В ВОПРОСАХ:
- "28 ноября 2025", "28.11.2025", "28/11/2025", "2025-11-28" = одна и та же дата
- "27 ноября", "27.11", "27/11" = 27 ноября (если год не указан, используй текущий год из данных)
- "с 1 по 5 ноября 2025", "от 1 до 5 ноября 2025", "1-5 ноября 2025" = период с 1 по 5 ноября
- "в ноябре 2025", "за ноябрь 2025" = весь ноябрь 2025 (с 1 по 30 ноября)
- "за сегодня", "сегодня" = текущая дата (если указана в данных)
- "за вчера", "вчера" = предыдущий день
- "за последнюю неделю" = последние 7 дней
- "за последний месяц" = последние 30 дней или текущий месяц

ПОЛЯ С ДАТАМИ В ДАННЫХ:
- video_created_at: дата и время создания видео (формат: "2025-11-15T10:00:00" или ISO 8601)
- snapshots[].created_at: дата и время снапшота статистики (формат: "2025-11-15T11:00:00")

СРАВНЕНИЕ ДАТ:
- Для сравнения дат извлекай только дату (без времени) из поля video_created_at или created_at
- "2025-11-15T10:00:00" -> дата: "2025-11-15"
- "2025-11-15T10:00:00" -> дата: "2025-11-15" (отбрасывай время)
- Сравнивай даты в формате YYYY-MM-DD
- "28 ноября 2025" = "2025-11-28"
- "27 ноября" = "2025-11-27" (если год не указан, используй год из данных)

РАСЧЕТЫ НА ОСНОВЕ ДАТ:
- "Сколько видео опубликовано 15 ноября 2025?" = найди видео где video_created_at содержит "2025-11-15", посчитай их количество
- "Сколько просмотров у видео, опубликованных в ноябре 2025?" = найди видео где video_created_at между "2025-11-01" и "2025-11-30", суммируй views_count
- "Сколько просмотров добавилось 28 ноября 2025?" = найди снапшоты где created_at содержит "2025-11-28", суммируй delta_views_count
- "Сколько лайков у видео за период с 1 по 5 ноября?" = найди видео где video_created_at между "2025-11-01" и "2025-11-05", суммируй likes_count
- "Какая статистика по видео с id X за 28 ноября?" = найди видео с id=X, затем найди снапшоты этого видео где created_at содержит "2025-11-28", верни нужное значение

СТРУКТУРА ДАННЫХ:
Данные представлены в формате JSON с массивом videos. Каждое видео имеет:
- id: идентификатор видео в формате UUID (строка, например: "ecd8a4e4-1f24-4b97-a944-35d17078ce7c")
  * UUID - это строка, НЕ число
  * Формат: 8-4-4-4-12 шестнадцатеричных символов, разделенных дефисами
  * При поиске сравнивай UUID как строку, точно, символ за символом
- creator_id: идентификатор креатора
- video_created_at: дата и время создания видео (формат ISO 8601, например: "2025-11-15T10:00:00")
- views_count: количество просмотров
- likes_count: количество лайков
- comments_count: количество комментариев
- reports_count: количество жалоб
- created_at: дата и время создания записи (формат ISO 8601)
- updated_at: дата и время обновления записи (формат ISO 8601)
- snapshots: массив снапшотов (почасовых замеров статистики)
  - id: идентификатор снапшота в формате UUID
  - video_id: идентификатор видео в формате UUID (должен совпадать с id видео)
  - views_count: текущее количество просмотров на момент замера
  - likes_count: текущее количество лайков на момент замера
  - comments_count: текущее количество комментариев на момент замера
  - reports_count: текущее количество жалоб на момент замера
  - delta_views_count: приращение просмотров с предыдущего замера
  - delta_likes_count: приращение лайков с предыдущего замера
  - delta_comments_count: приращение комментариев с предыдущего замера
  - delta_reports_count: приращение жалоб с предыдущего замера
  - created_at: дата и время создания снапшота (формат ISO 8601, например: "2025-11-30T12:00:14.355067+00:00")
  - updated_at: дата и время обновления снапшота (формат ISO 8601, например: "2025-11-30T12:00:14.355067+00:00")

ВАЖНО ДЛЯ ПОИСКА:
- Чтобы найти конкретное видео, ищи в массиве videos элемент, где поле "id" совпадает с указанным UUID
- ID видео ВСЕГДА в формате UUID (например: ecd8a4e4-1f24-4b97-a944-35d17078ce7c)
- UUID состоит из 32 шестнадцатеричных символов (0-9, a-f, A-F), разделенных дефисами в формате: 8-4-4-4-12
- Сравнивай UUID ТОЧНО, символ за символом, учитывая регистр (case-sensitive)
- НЕ преобразуй UUID в другой формат, НЕ изменяй регистр, НЕ удаляй дефисы
- После нахождения видео по UUID, извлекай нужное поле (views_count, likes_count и т.д.)

ПРИМЕРЫ:

Вопрос: "Какая статистика по видео с id ecd8a4e4-1f24-4b97-a944-35d17078ce7c?"
Ответ: 15000
(найди видео с этим id, верни views_count)

Вопрос: "Сколько просмотров у видео с id ecd8a4e4-1f24-4b97-a944-35d17078ce7c?"
Ответ: 15000

Вопрос: "Сколько лайков у видео ecd8a4e4-1f24-4b97-a944-35d17078ce7c?"
Ответ: 500

Вопрос: "Какое количество комментариев у видео с id ecd8a4e4-1f24-4b97-a944-35d17078ce7c?"
Ответ: 25

Вопрос: "Сколько всего просмотров у всех видео?"
Ответ: 3326609

Вопрос: "Сколько видео в файле?"
Ответ: 150

Вопрос: "Какое общее количество лайков?"
Ответ: 85234

Вопрос: "Какое максимальное количество просмотров?"
Ответ: 150000

ПРИМЕРЫ С ДАТАМИ:

Вопрос: "Сколько видео опубликовано 15 ноября 2025?"
Ответ: 25
(найди видео где video_created_at содержит "2025-11-15", посчитай количество)

Вопрос: "Сколько просмотров у видео, опубликованных 15 ноября 2025?"
Ответ: 150000
(найди видео где video_created_at содержит "2025-11-15", суммируй views_count)

Вопрос: "Сколько видео вышло в ноябре 2025?"
Ответ: 50
(найди видео где video_created_at между "2025-11-01" и "2025-11-30", посчитай количество)

Вопрос: "Сколько просмотров у видео, опубликованных в ноябре 2025?"
Ответ: 500000
(найди видео где video_created_at между "2025-11-01" и "2025-11-30", суммируй views_count)

Вопрос: "Сколько просмотров добавилось 28 ноября 2025?"
Ответ: 5000
(найди снапшоты где created_at содержит "2025-11-28", суммируй delta_views_count)

Вопрос: "На сколько увеличились лайки всех видео за 28 ноября 2025?"
Ответ: 250
(найди снапшоты где created_at содержит "2025-11-28", суммируй delta_likes_count)

Вопрос: "Сколько лайков у видео за период с 1 по 5 ноября 2025?"
Ответ: 10000
(найди видео где video_created_at между "2025-11-01" и "2025-11-05", суммируй likes_count)

Вопрос: "Какая статистика по видео с id ecd8a4e4-1f24-4b97-a944-35d17078ce7c за 28 ноября?"
Ответ: 1500
(найди видео с id, затем найди снапшоты этого видео где created_at содержит "2025-11-28", верни views_count или delta_views_count в зависимости от вопроса)

Вопрос: "Сколько просмотров у видео, опубликованных с 1 по 5 ноября включительно?"
Ответ: 75000
(найди видео где video_created_at между "2025-11-01" и "2025-11-05", суммируй views_count)

Вопрос: "Сколько видео создано 27 ноября?"
Ответ: 10
(найди видео где video_created_at содержит "2025-11-27", посчитай количество)

ВАЖНО:
- ВСЕГДА ищи конкретные видео по ID в массиве videos
- ВСЕГДА правильно обрабатывай даты: сравнивай только дату (без времени) из полей video_created_at и created_at
- При сравнении дат извлекай дату в формате YYYY-MM-DD из ISO 8601 строк (например: "2025-11-15T10:00:00" -> "2025-11-15")
- Для вопросов про период используй диапазон дат (BETWEEN или >= и <=)
- Для вопросов про снапшоты ищи в массиве snapshots каждого видео по полю created_at
- Всегда возвращай ТОЛЬКО число без текста, пробелов и символов форматирования
- Если видео не найдено или данных нет, верни 0

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

            # Логируем дополнительную информацию, если результат 0
            if number == "0":
                # Проверяем, содержит ли вопрос UUID
                uuid_in_question = re.search(
                    r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}',
                    question
                )
                uuid_found = uuid_in_question.group(0) if uuid_in_question else None

                # Если в вопросе есть UUID, проверяем, есть ли такое видео в данных
                video_found = False
                if uuid_found and isinstance(self.current_data, dict):
                    videos = self.current_data.get('videos', [])
                    video_found = any(
                        str(v.get('id', '')) == uuid_found for v in videos
                    )

                logger.warning(
                    "Результат равен 0",
                    question=question[:200],
                    original_response=text[:200],
                    has_uuid_in_question=(uuid_found is not None),
                    uuid_in_question=uuid_found,
                    video_found_in_data=video_found,
                    data_context_length=len(data_context),
                    videos_count=len(self.current_data.get('videos', [])) if isinstance(self.current_data, dict) else 0
                )

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
