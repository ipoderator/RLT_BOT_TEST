"""
Telegram бот для аналитики видео.
Принимает запросы на русском языке и возвращает результаты в виде чисел.
Поддерживает загрузку JSON файлов для анализа через GigaChat.
"""
import os
import asyncio
import tempfile
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from loguru import logger
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, BotCommand
from query_executor import VideoAnalytics
from file_analyzer import FileAnalyzer

# Импортируем исключения GigaChat для обработки ошибок API
try:
    from gigachat.exceptions import ResponseError
except ImportError:
    # Если модуль не найден, создаем заглушку
    ResponseError = Exception

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования loguru
# Удаляем стандартный обработчик
logger.remove()

# Добавляем обработчик для консоли с цветным выводом
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
           "<level>{message}</level>",
    level="INFO",
    colorize=True
)

# Добавляем обработчик для файла с подробной информацией
logs_dir = Path(__file__).parent / "logs"
logs_dir.mkdir(exist_ok=True)
log_file = logs_dir / "bot_{time:YYYY-MM-DD}.log"

logger.add(
    log_file,
    format=(
        "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
        "{name}:{function}:{line} | {message}"
    ),
    level="DEBUG",
    rotation="00:00",  # Ротация в полночь
    retention="30 days",  # Хранить логи 30 дней
    compression="zip",  # Сжимать старые логи
    encoding="utf-8",
    backtrace=True,  # Показывать полный стек вызовов
    diagnose=True,  # Показывать значения переменных при ошибках
)

# Инициализация бота и диспетчера
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL не найден в переменных окружения")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Глобальный объект аналитики
analytics: Optional[VideoAnalytics] = None
file_analyzer: Optional[FileAnalyzer] = None


async def set_bot_commands():
    """Устанавливает меню команд бота."""
    commands = [
        BotCommand(
            command="start", description="Начать работу с ботом"
        ),
        BotCommand(
            command="clear_file", description="Очистить загруженный файл"
        ),
        BotCommand(
            command="check", description="Передать ссылку на репозиторий"
        ),
        BotCommand(
            command="total_videos",
            description="Сколько всего видео в системе?"
        ),
        BotCommand(
            command="total_views",
            description="Какое общее количество просмотров?"
        ),
        BotCommand(
            command="total_likes",
            description="Сколько всего лайков?"
        ),
        BotCommand(
            command="popular_videos",
            description="Сколько видео с >100000 просмотров?"
        ),
    ]
    await bot.set_my_commands(commands)
    logger.info("Меню команд бота установлено")


@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start."""
    await message.answer(
        "Привет! Я бот для аналитики видео.\n\n"
        "📊 Режимы работы:\n"
        "1. Анализ данных из базы данных - "
        "задавайте вопросы на русском языке\n"
        "2. Анализ загруженного JSON файла - "
        "отправьте файл, затем задавайте вопросы\n\n"
        "⚡ Быстрые команды:\n"
        "Используйте меню команд (нажмите / в поле ввода) "
        "для быстрого доступа:\n"
        "• /total_videos - Сколько всего видео?\n"
        "• /total_views - Общее количество просмотров\n"
        "• /total_likes - Общее количество лайков\n"
        "• /popular_videos - Популярные видео (>100k просмотров)\n\n"
        "📁 Для анализа файла:\n"
        "• Отправьте JSON файл с данными о видео\n"
        "• После загрузки задавайте вопросы на основе данных из файла\n"
        "• Используйте /clear_file чтобы очистить загруженный файл\n\n"
        "💡 Примеры вопросов:\n"
        "• Сколько всего видео есть в системе?\n"
        "• Сколько видео набрало больше 100000 просмотров?\n"
        "• На сколько просмотров выросли все видео "
        "28 ноября 2025?\n"
        "• Сколько разных видео получали новые просмотры "
        "27 ноября 2025?"
    )


@dp.message(Command("clear_file"))
async def cmd_clear_file(message: Message):
    """Обработчик команды /clear_file - очищает загруженный файл."""
    global file_analyzer

    if file_analyzer and file_analyzer.has_data():
        cached_info = file_analyzer.get_cached_file_info()
        file_name = (
            cached_info.get('file_name', 'файл')
            if cached_info else 'файл'
        )

        file_analyzer.clear_data()
        await message.answer(
            f"✅ Загруженный файл '{file_name}' очищен из памяти и кэша. "
            "Теперь бот будет использовать данные из базы данных."
        )
    else:
        await message.answer("ℹ️ Нет загруженного файла для очистки.")


@dp.message(Command("check"))
async def cmd_check(message: Message):
    """Обработчик команды /check - принимает ссылку на репозиторий."""
    import re

    # Извлекаем текст после команды /check
    text = message.text or ""
    # Убираем команду /check и лишние пробелы
    url_text = text.replace("/check", "").strip()

    # Если URL не указан, просим его предоставить
    if not url_text:
        await message.answer(
            "📋 Пожалуйста, укажите ссылку на репозиторий "
            "после команды /check.\n\n"
            "Примеры:\n"
            "• /check https://github.com/username/repo\n"
            "• /check https://gitlab.com/username/repo\n"
            "• /check https://bitbucket.org/username/repo"
        )
        return

    # Валидируем URL репозитория
    # Поддерживаемые форматы:
    # - https://github.com/username/repo
    # - https://gitlab.com/username/repo
    # - https://bitbucket.org/username/repo
    # - http:// варианты тоже поддерживаем

    url_patterns = [
        r'https?://github\.com/[\w\-\.]+/[\w\-\.]+',
        r'https?://gitlab\.com/[\w\-\.]+/[\w\-\.]+',
        r'https?://bitbucket\.org/[\w\-\.]+/[\w\-\.]+',
    ]

    is_valid = False
    for pattern in url_patterns:
        if re.match(pattern, url_text):
            is_valid = True
            break

    if not is_valid:
        await message.answer(
            "❌ Неверный формат ссылки на репозиторий.\n\n"
            "Поддерживаются репозитории:\n"
            "• GitHub: https://github.com/username/repo\n"
            "• GitLab: https://gitlab.com/username/repo\n"
            "• Bitbucket: https://bitbucket.org/username/repo\n\n"
            "Пожалуйста, проверьте ссылку и попробуйте снова."
        )
        return

    # Логируем полученную ссылку
    logger.info(
        "Получена ссылка на репозиторий",
        repository_url=url_text,
        user_id=message.from_user.id if message.from_user else None,
        username=message.from_user.username if message.from_user else None
    )

    # Определяем тип репозитория
    repo_type = "неизвестный"
    if "github.com" in url_text:
        repo_type = "GitHub"
    elif "gitlab.com" in url_text:
        repo_type = "GitLab"
    elif "bitbucket.org" in url_text:
        repo_type = "Bitbucket"

    # Отвечаем пользователю
    await message.answer(
        f"✅ Ссылка на репозиторий получена!\n\n"
        f"🔗 Репозиторий: {url_text}\n"
        f"📦 Платформа: {repo_type}\n\n"
        f"Ссылка сохранена и будет использована для проверки проекта."
    )


@dp.message(Command("total_videos"))
async def cmd_total_videos(message: Message):
    """Быстрая команда: Сколько всего видео в системе?"""
    await handle_message_with_query(
        message, "Сколько всего видео есть в системе?"
    )


@dp.message(Command("total_views"))
async def cmd_total_views(message: Message):
    """Быстрая команда: Какое общее количество просмотров?"""
    await handle_message_with_query(
        message, "Какое общее количество просмотров всех видео?"
    )


@dp.message(Command("total_likes"))
async def cmd_total_likes(message: Message):
    """Быстрая команда: Сколько всего лайков?"""
    await handle_message_with_query(
        message, "Сколько всего лайков у всех видео?"
    )


@dp.message(Command("popular_videos"))
async def cmd_popular_videos(message: Message):
    """Быстрая команда: Сколько видео с более чем 100000 просмотров?"""
    await handle_message_with_query(
        message, "Сколько видео набрало больше 100000 просмотров?"
    )


async def handle_message_with_query(message: Message, query: str):
    """
    Обрабатывает сообщение с заданным запросом.

    Args:
        message: Сообщение от пользователя
        query: Текст запроса для обработки
    """
    global analytics, file_analyzer

    # Проверяем, есть ли загруженный файл
    use_file_analyzer = file_analyzer and file_analyzer.has_data()

    if use_file_analyzer:
        # Используем анализатор файлов
        processing_msg = await message.answer(
            "📊 Анализирую данные из загруженного файла..."
        )

        try:
            answer = await file_analyzer.answer_question(query)

            try:
                await processing_msg.delete()
            except Exception:
                pass

            await message.answer(answer)

        except Exception as e:
            logger.error(
                "Ошибка при обработке запроса через file_analyzer",
                query=query,
                error=str(e),
                error_type=type(e).__name__
            )

            try:
                await processing_msg.delete()
            except Exception:
                pass

            error_msg = str(e)
            error_type = type(e).__name__

            # Специальная обработка ошибок GigaChat API
            is_gigachat_error = (
                isinstance(e, ResponseError) or
                "ResponseError" in error_type
            )
            if is_gigachat_error:
                # Проверяем код статуса ошибки
                status_code = None
                if hasattr(e, 'status_code'):
                    status_code = e.status_code
                elif "402" in error_msg or "Payment Required" in error_msg:
                    status_code = 402
                elif "401" in error_msg or "Unauthorized" in error_msg:
                    status_code = 401
                elif "429" in error_msg or "Too Many Requests" in error_msg:
                    status_code = 429
                elif ("500" in error_msg or
                      "Internal Server Error" in error_msg):
                    status_code = 500

                if status_code == 402:
                    user_message = (
                        "❌ Ошибка доступа к GigaChat API: "
                        "требуется оплата.\n\n"
                        "У вашего аккаунта GigaChat закончились средства "
                        "или квота.\n\n"
                        "Пожалуйста:\n"
                        "• Проверьте баланс на платформе GigaChat\n"
                        "• Пополните счет или увеличьте квоту\n"
                        "• Используйте /clear_file для возврата к анализу "
                        "данных из базы"
                    )
                elif status_code == 401:
                    user_message = (
                        "❌ Ошибка авторизации GigaChat API.\n\n"
                        "Неверные учетные данные или токен истек.\n\n"
                        "Пожалуйста, обратитесь к администратору для "
                        "обновления учетных данных GigaChat."
                    )
                elif status_code == 429:
                    user_message = (
                        "⏱️ Превышен лимит запросов к GigaChat API.\n\n"
                        "Слишком много запросов за короткое время.\n\n"
                        "Пожалуйста, подождите несколько минут и "
                        "попробуйте снова."
                    )
                elif status_code == 500:
                    user_message = (
                        "🔧 Временная ошибка сервера GigaChat API.\n\n"
                        "Сервис временно недоступен.\n\n"
                        "Пожалуйста, попробуйте позже или используйте "
                        "/clear_file для возврата к анализу данных из базы."
                    )
                else:
                    user_message = (
                        f"❌ Ошибка GigaChat API "
                        f"(код {status_code or 'неизвестен'}):\n\n"
                        f"{error_msg[:200]}\n\n"
                        "Попробуйте позже или используйте /clear_file для "
                        "возврата к анализу данных из базы."
                    )
            elif ("не загружены" in error_msg.lower() or
                    "not loaded" in error_msg.lower()):
                user_message = (
                    "Данные не загружены. Пожалуйста, отправьте JSON файл."
                )
            else:
                user_message = (
                    f"Произошла ошибка при анализе данных: "
                    f"{error_msg[:200]}\n\n"
                    "Попробуйте переформулировать вопрос или используйте "
                    "/clear_file для возврата к анализу данных из базы."
                )

            await message.answer(user_message)

        return

    # Используем систему аналитики из базы данных
    if analytics is None:
        await message.answer(
            "Система аналитики не инициализирована. "
            "Пожалуйста, подождите или обратитесь к администратору."
        )
        return

    # Показываем, что бот обрабатывает запрос
    processing_msg = await message.answer("Обрабатываю запрос...")

    try:
        # Получаем ответ от системы аналитики
        answer = await analytics.answer_question(query)

        # Удаляем сообщение "Обрабатываю запрос..."
        try:
            await processing_msg.delete()
        except Exception:
            pass

        # Отправляем ответ пользователю
        await message.answer(answer)

    except Exception as e:
        logger.error(
            "Ошибка при обработке запроса",
            query=query,
            error=str(e),
            error_type=type(e).__name__,
            user_id=message.from_user.id if message.from_user else None
        )

        # Удаляем сообщение "Обрабатываю запрос..."
        try:
            await processing_msg.delete()
        except Exception:
            pass

        # Формируем понятное сообщение об ошибке
        error_msg = str(e)
        if "SQL" in error_msg or "запрос" in error_msg.lower():
            user_message = (
                "Не удалось сформировать SQL запрос для вашего вопроса.\n\n"
                "Попробуйте переформулировать вопрос более конкретно."
            )
        elif ("подключ" in error_msg.lower() or
              "connection" in error_msg.lower()):
            user_message = (
                "Ошибка подключения к базе данных или API.\n"
                "Пожалуйста, обратитесь к администратору."
            )
        else:
            user_message = (
                f"Произошла ошибка: {error_msg}\n\n"
                "Попробуйте переформулировать вопрос или обратитесь "
                "к администратору."
            )

        await message.answer(user_message)


@dp.message(lambda message: message.document is not None)
async def handle_document(message: Message):
    """Обработчик загрузки документов (JSON файлов)."""
    global file_analyzer

    if not file_analyzer:
        await message.answer(
            "❌ Анализатор файлов не инициализирован. "
            "Пожалуйста, обратитесь к администратору."
        )
        return

    # Проверяем, что это JSON файл
    document = message.document
    file_name = (
        document.file_name.lower()
        if document.file_name
        else ""
    )

    if not file_name.endswith('.json'):
        await message.answer(
            "❌ Пожалуйста, отправьте JSON файл "
            "(с расширением .json)"
        )
        return

    # Проверяем размер файла (максимум 50 МБ)
    max_file_size = 50 * 1024 * 1024  # 50 МБ
    if document.file_size and document.file_size > max_file_size:
        file_size_mb = document.file_size / 1024 / 1024
        max_size_mb = max_file_size / 1024 / 1024
        await message.answer(
            f"❌ Файл слишком большой ({file_size_mb:.1f} МБ). "
            f"Максимальный размер: {max_size_mb} МБ."
        )
        return

    # Показываем, что бот обрабатывает файл
    processing_msg = await message.answer("📥 Загружаю и анализирую файл...")

    tmp_path = None
    status_update_task = None

    async def update_status_periodically():
        """Периодически обновляет статус загрузки для больших файлов."""
        status_messages = [
            "📥 Загружаю файл...",
            "📥 Загрузка продолжается...",
            "📥 Обрабатываю большой файл, подождите...",
            "📥 Файл загружается, это может занять время...",
        ]
        counter = 0
        while True:
            await asyncio.sleep(30)  # Обновляем каждые 30 секунд
            try:
                status_text = status_messages[counter % len(status_messages)]
                await processing_msg.edit_text(status_text)
                counter += 1
            except Exception:
                # Если не удалось обновить сообщение, продолжаем
                pass

    try:
        # Скачиваем файл с таймаутом
        file = await bot.get_file(document.file_id)

        # Определяем таймаут в зависимости от размера файла
        # Для файлов больше 10 МБ увеличиваем таймаут до 15 минут
        file_size_mb = (document.file_size or 0) / 1024 / 1024
        if file_size_mb > 10:
            download_timeout = 900  # 15 минут для больших файлов
            # Запускаем периодические обновления статуса
            status_update_task = asyncio.create_task(
                update_status_periodically()
            )
        elif file_size_mb > 5:
            download_timeout = 600  # 10 минут для средних файлов
            status_update_task = asyncio.create_task(
                update_status_periodically()
            )
        else:
            download_timeout = 300  # 5 минут для маленьких файлов

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(
            mode='wb', delete=False, suffix='.json'
        ) as tmp_file:
            tmp_path = tmp_file.name

        # Загружаем файл с таймаутом и обработкой ошибок
        try:
            logger.info(
                f"Начало загрузки файла: {document.file_name}, "
                f"размер: {file_size_mb:.2f} МБ, таймаут: {download_timeout}с"
            )

            await asyncio.wait_for(
                bot.download_file(file.file_path, tmp_path),
                timeout=download_timeout
            )

            logger.info(f"Файл успешно загружен: {document.file_name}")

            # Останавливаем задачу обновления статуса
            if status_update_task:
                status_update_task.cancel()
                try:
                    await status_update_task
                except asyncio.CancelledError:
                    pass

        except asyncio.TimeoutError:
            # Отменяем задачу обновления статуса
            if status_update_task:
                status_update_task.cancel()
                try:
                    await status_update_task
                except asyncio.CancelledError:
                    pass

            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
            try:
                await processing_msg.delete()
            except Exception:
                pass

            # Формируем более информативное сообщение
            timeout_minutes = download_timeout // 60
            await message.answer(
                f"❌ Превышено время ожидания при загрузке файла.\n\n"
                f"Файл '{document.file_name}' ({file_size_mb:.1f} МБ) "
                f"слишком большой или соединение нестабильно.\n\n"
                f"Таймаут загрузки: {timeout_minutes} минут.\n\n"
                f"Попробуйте:\n"
                "• Отправить файл меньшего размера (рекомендуется до 10 МБ)\n"
                "• Проверить интернет-соединение\n"
                "• Разделить файл на несколько частей\n"
                "• Попробовать позже"
            )
            logger.warning(
                "Таймаут при загрузке файла",
                file_name=document.file_name,
                file_size=document.file_size,
                file_size_mb=file_size_mb,
                timeout=download_timeout,
                user_id=message.from_user.id if message.from_user else None
            )
            return

        try:
            # Загружаем JSON и сохраняем в кэш
            file_analyzer.load_json_file(tmp_path, cache=True)

            # Удаляем временный файл (файл уже сохранен в кэш)
            os.unlink(tmp_path)
            tmp_path = None

            # Удаляем сообщение "Загружаю..."
            try:
                await processing_msg.delete()
            except Exception:
                pass

            cached_info = file_analyzer.get_cached_file_info()
            cache_note = ""
            if cached_info:
                cache_note = (
                    "\n\n💾 Файл сохранен в кэш и будет автоматически "
                    "загружаться при следующем запуске бота."
                )

            await message.answer(
                f"✅ Файл '{document.file_name}' успешно загружен "
                f"и проанализирован!{cache_note}\n\n"
                "Теперь вы можете задавать вопросы на основе данных "
                "из этого файла.\n\n"
                "Примеры вопросов:\n"
                "• Сколько всего видео в файле?\n"
                "• Какое общее количество просмотров?\n"
                "• Сколько лайков у всех видео?\n"
                "• Какая статистика по видео с id X?\n\n"
                "Используйте /clear_file чтобы вернуться к анализу "
                "данных из базы."
            )

        except ValueError as json_error:
            # Отменяем задачу обновления статуса при ошибке JSON
            if status_update_task:
                status_update_task.cancel()
                try:
                    await status_update_task
                except asyncio.CancelledError:
                    pass

            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await message.answer(
                f"❌ Ошибка при обработке JSON файла: {str(json_error)}\n\n"
                "Убедитесь, что файл содержит корректный JSON."
            )
        except Exception as inner_error:
            # Отменяем задачу обновления статуса при внутренней ошибке
            if status_update_task:
                status_update_task.cancel()
                try:
                    await status_update_task
                except asyncio.CancelledError:
                    pass

            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            try:
                await processing_msg.delete()
            except Exception as delete_error:
                logger.debug(
                    "Не удалось удалить сообщение",
                    error=str(delete_error)
                )
            raise inner_error

    except Exception as e:
        # Отменяем задачу обновления статуса при любой ошибке
        if status_update_task:
            status_update_task.cancel()
            try:
                await status_update_task
            except asyncio.CancelledError:
                pass

        logger.exception(
            "Ошибка при загрузке файла",
            file_name=document.file_name if document else None,
            file_size=document.file_size if document else None,
            user_id=message.from_user.id if message.from_user else None,
            error=str(e),
            error_type=type(e).__name__
        )
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception as cleanup_error:
                logger.debug(
                    "Не удалось удалить временный файл",
                    file_path=tmp_path,
                    error=str(cleanup_error)
                )
        try:
            await processing_msg.delete()
        except Exception as delete_error:
            logger.debug(
                "Не удалось удалить сообщение",
                error=str(delete_error)
            )

        # Формируем более информативное сообщение об ошибке
        error_message = str(e)
        error_type = type(e).__name__

        # Специальная обработка для таймаута
        is_timeout = isinstance(e, (asyncio.TimeoutError, TimeoutError))
        if is_timeout or "timeout" in error_message.lower():
            user_message = (
                f"⏱️ Превышено время ожидания при загрузке файла.\n\n"
                f"Файл '{document.file_name if document else 'файл'}' "
                f"слишком большой или соединение нестабильно.\n\n"
                f"Попробуйте:\n"
                f"• Отправить файл меньшего размера "
                f"(рекомендуется до 10 МБ)\n"
                f"• Проверить интернет-соединение\n"
                f"• Попробовать позже"
            )
        elif "JSON" in error_message or "json" in error_message.lower():
            user_message = (
                f"❌ Ошибка при обработке JSON файла: {error_message}\n\n"
                "Убедитесь, что файл содержит корректный JSON формат."
            )
        has_cache = "кэш" in error_message.lower()
        if has_cache or "cache" in error_message.lower():
            user_message = (
                f"⚠️ Файл загружен, но не удалось сохранить в кэш: "
                f"{error_message}\n\n"
                "Файл будет работать до перезапуска бота. "
                "Попробуйте отправить файл еще раз."
            )
        has_conn = "connection" in error_message.lower()
        if has_conn or "соединен" in error_message.lower():
            user_message = (
                "🌐 Ошибка соединения при загрузке файла.\n\n"
                "Проверьте интернет-соединение и попробуйте "
                "отправить файл еще раз."
            )
        has_perm = "permission" in error_message.lower()
        if has_perm or "доступ" in error_message.lower():
            user_message = (
                "🔒 Ошибка доступа при сохранении файла.\n\n"
                "Пожалуйста, обратитесь к администратору."
            )
        else:
            user_message = (
                f"❌ Произошла ошибка при загрузке файла.\n\n"
                f"Тип ошибки: {error_type}\n"
                f"Сообщение: {error_message[:200]}\n\n"
                f"Попробуйте:\n"
                f"• Отправить файл еще раз\n"
                f"• Проверить формат файла (должен быть JSON)\n"
                f"• Обратиться к администратору"
            )

        await message.answer(user_message)


@dp.message()
async def handle_message(message: Message):
    """Обработчик текстовых сообщений."""
    global analytics, file_analyzer

    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    user_query = message.text.strip()

    if not user_query:
        await message.answer("Пожалуйста, задайте вопрос.")
        return

    # Проверяем, есть ли загруженный файл
    use_file_analyzer = file_analyzer and file_analyzer.has_data()

    if use_file_analyzer:
        # Используем анализатор файлов
        processing_msg = await message.answer(
            "📊 Анализирую данные из загруженного файла..."
        )

        try:
            answer = await file_analyzer.answer_question(user_query)

            try:
                await processing_msg.delete()
            except Exception:
                pass

            await message.answer(answer)

        except Exception as e:
            logger.error(
                "Ошибка при обработке запроса через file_analyzer",
                query=user_query,
                error=str(e),
                error_type=type(e).__name__,
                user_id=message.from_user.id if message.from_user else None
            )

            try:
                await processing_msg.delete()
            except Exception:
                pass

            error_msg = str(e)
            error_type = type(e).__name__

            # Специальная обработка ошибок GigaChat API
            is_gigachat_error = (
                isinstance(e, ResponseError) or
                "ResponseError" in error_type
            )
            if is_gigachat_error:
                # Проверяем код статуса ошибки
                status_code = None
                if hasattr(e, 'status_code'):
                    status_code = e.status_code
                elif "402" in error_msg or "Payment Required" in error_msg:
                    status_code = 402
                elif "401" in error_msg or "Unauthorized" in error_msg:
                    status_code = 401
                elif "429" in error_msg or "Too Many Requests" in error_msg:
                    status_code = 429
                elif ("500" in error_msg or
                      "Internal Server Error" in error_msg):
                    status_code = 500

                if status_code == 402:
                    user_message = (
                        "❌ Ошибка доступа к GigaChat API: "
                        "требуется оплата.\n\n"
                        "У вашего аккаунта GigaChat закончились средства "
                        "или квота.\n\n"
                        "Пожалуйста:\n"
                        "• Проверьте баланс на платформе GigaChat\n"
                        "• Пополните счет или увеличьте квоту\n"
                        "• Используйте /clear_file для возврата к анализу "
                        "данных из базы"
                    )
                elif status_code == 401:
                    user_message = (
                        "❌ Ошибка авторизации GigaChat API.\n\n"
                        "Неверные учетные данные или токен истек.\n\n"
                        "Пожалуйста, обратитесь к администратору для "
                        "обновления учетных данных GigaChat."
                    )
                elif status_code == 429:
                    user_message = (
                        "⏱️ Превышен лимит запросов к GigaChat API.\n\n"
                        "Слишком много запросов за короткое время.\n\n"
                        "Пожалуйста, подождите несколько минут и "
                        "попробуйте снова."
                    )
                elif status_code == 500:
                    user_message = (
                        "🔧 Временная ошибка сервера GigaChat API.\n\n"
                        "Сервис временно недоступен.\n\n"
                        "Пожалуйста, попробуйте позже или используйте "
                        "/clear_file для возврата к анализу данных из базы."
                    )
                else:
                    user_message = (
                        f"❌ Ошибка GigaChat API "
                        f"(код {status_code or 'неизвестен'}):\n\n"
                        f"{error_msg[:200]}\n\n"
                        "Попробуйте позже или используйте /clear_file для "
                        "возврата к анализу данных из базы."
                    )
            elif ("не загружены" in error_msg.lower() or
                    "not loaded" in error_msg.lower()):
                user_message = (
                    "Данные не загружены. Пожалуйста, отправьте JSON файл."
                )
            else:
                user_message = (
                    f"Произошла ошибка при анализе данных: "
                    f"{error_msg[:200]}\n\n"
                    "Попробуйте переформулировать вопрос или используйте "
                    "/clear_file для возврата к анализу данных из базы."
                )

            await message.answer(user_message)

        return

    # Используем систему аналитики из базы данных
    if analytics is None:
        await message.answer(
            "Система аналитики не инициализирована. "
            "Пожалуйста, подождите или обратитесь к администратору."
        )
        return

    # Показываем, что бот обрабатывает запрос
    processing_msg = await message.answer("Обрабатываю запрос...")

    try:
        # Получаем ответ от системы аналитики
        answer = await analytics.answer_question(user_query)

        # Удаляем сообщение "Обрабатываю запрос..."
        try:
            await processing_msg.delete()
        except Exception:
            pass

        # Отправляем ответ пользователю
        await message.answer(answer)

    except Exception as e:
        logger.error(
            "Ошибка при обработке запроса",
            query=user_query,
            error=str(e),
            error_type=type(e).__name__,
            user_id=message.from_user.id if message.from_user else None
        )

        # Удаляем сообщение "Обрабатываю запрос..."
        try:
            await processing_msg.delete()
        except Exception:
            pass

        # Формируем понятное сообщение об ошибке
        error_msg = str(e)
        if "SQL" in error_msg or "запрос" in error_msg.lower():
            user_message = (
                "Не удалось сформировать SQL запрос для вашего вопроса.\n\n"
                "Попробуйте переформулировать вопрос более конкретно, "
                "например:\n"
                "• Сколько всего видео в системе?\n"
                "• Сколько просмотров у всех видео?\n"
                "• На сколько выросли просмотры 28 ноября 2025?"
            )
        elif ("подключ" in error_msg.lower() or
              "connection" in error_msg.lower()):
            user_message = (
                "Ошибка подключения к базе данных или API.\n"
                "Пожалуйста, обратитесь к администратору."
            )
        else:
            user_message = (
                f"Произошла ошибка: {error_msg}\n\n"
                "Попробуйте переформулировать вопрос или "
                "обратитесь к администратору."
            )

        await message.answer(user_message)


async def main():
    """Главная функция для запуска бота."""
    global analytics, file_analyzer

    logger.info("Инициализация системы аналитики...")

    try:
        # Создаем объект аналитики для работы с БД
        analytics = VideoAnalytics(
            db_url=DATABASE_URL,
            gigachat_credentials=GIGACHAT_CREDENTIALS,
            gigachat_scope=GIGACHAT_SCOPE
        )

        # Создаем анализатор файлов
        if GIGACHAT_CREDENTIALS:
            file_analyzer = FileAnalyzer(
                gigachat_credentials=GIGACHAT_CREDENTIALS,
                gigachat_scope=GIGACHAT_SCOPE
            )

            # Пытаемся загрузить файл из кэша
            if file_analyzer.load_cached_file():
                cached_info = file_analyzer.get_cached_file_info()
                if cached_info:
                    logger.info(
                        f"Загружен файл из кэша: "
                        f"{cached_info.get('file_name', 'unknown')} "
                        f"(закэширован "
                        f"{cached_info.get('cached_at', 'unknown')})"
                    )
                else:
                    logger.info("Файл загружен из кэша")
            else:
                logger.info("Кэш пуст, файл не загружен")

            logger.info("Анализатор файлов инициализирован")
        else:
            logger.warning(
                "GIGACHAT_CREDENTIALS не найден, "
                "анализатор файлов недоступен"
            )

        logger.info("Система аналитики инициализирована")

        # Устанавливаем меню команд бота
        await set_bot_commands()

        logger.info("Запуск бота...")

        # Запускаем бота
        await dp.start_polling(bot)

    except Exception as e:
        logger.exception(
            "Критическая ошибка при работе бота",
            error=str(e),
            error_type=type(e).__name__
        )
        raise
    finally:
        # Закрываем соединения
        if analytics:
            await analytics.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.exception(
            "Ошибка при запуске бота",
            error=str(e),
            error_type=type(e).__name__
        )
