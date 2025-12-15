"""
Модуль для анализа загруженных JSON файлов и ответов на вопросы через GigaChat.
"""
import json
import logging
import asyncio
import re
from typing import Optional, Dict, Any, List
from gigachat import GigaChat

logger = logging.getLogger(__name__)


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
    
    def _get_client(self) -> GigaChat:
        """Получает или создает клиент GigaChat."""
        if self._client is None:
            self._client = GigaChat(
                credentials=self.credentials,
                scope=self.scope,
                verify_ssl_certs=False
            )
        return self._client
    
    def load_json_file(self, file_path: str) -> Dict[str, Any]:
        """
        Загружает JSON файл.
        
        Args:
            file_path: Путь к JSON файлу
            
        Returns:
            Словарь с данными из файла
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.current_data = data
            logger.info(f"Файл {file_path} успешно загружен")
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Ошибка парсинга JSON: {e}")
        except FileNotFoundError:
            raise FileNotFoundError(f"Файл {file_path} не найден")
        except Exception as e:
            raise Exception(f"Ошибка при загрузке файла: {e}")
    
    def load_json_from_bytes(self, file_bytes: bytes) -> Dict[str, Any]:
        """
        Загружает JSON из байтов.
        
        Args:
            file_bytes: Байты JSON файла
            
        Returns:
            Словарь с данными из файла
        """
        try:
            data = json.loads(file_bytes.decode('utf-8'))
            self.current_data = data
            logger.info("JSON данные успешно загружены из байтов")
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Ошибка парсинга JSON: {e}")
        except Exception as e:
            raise Exception(f"Ошибка при загрузке JSON: {e}")
    
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
            logger.info(f"Данные слишком большие ({len(json_str)} символов), создаю сводку")
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
            
            logger.info(f"Ответ от GigaChat получен: {text[:100]}...")
            
            # Извлекаем число из ответа
            number = self._extract_number(text)
            
            return number
            
        except Exception as e:
            logger.error(f"Ошибка при обработке вопроса: {e}", exc_info=True)
            raise Exception(f"Ошибка при обработке вопроса: {e}")
    
    def has_data(self) -> bool:
        """Проверяет, загружены ли данные."""
        return self.current_data is not None
    
    def clear_data(self):
        """Очищает загруженные данные."""
        self.current_data = None
        logger.info("Данные очищены")

