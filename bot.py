"""
Telegram бот для аналитики видео.
Принимает запросы на русском языке и возвращает результаты в виде чисел.
Поддерживает загрузку JSON файлов для анализа через GigaChat.
"""
import os
import asyncio
import logging
import tempfile
from typing import Optional
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, BotCommand
from query_executor import VideoAnalytics
from file_analyzer import FileAnalyzer

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        BotCommand(command="start", description="Начать работу с ботом"),
        BotCommand(command="clear_file", description="Очистить загруженный файл"),
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
        "1. Анализ данных из базы данных - задавайте вопросы на русском языке\n"
        "2. Анализ загруженного JSON файла - отправьте файл, затем задавайте вопросы\n\n"
        "⚡ Быстрые команды:\n"
        "Используйте меню команд (нажмите / в поле ввода) для быстрого доступа:\n"
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
        "• На сколько просмотров выросли все видео 28 ноября 2025?\n"
        "• Сколько разных видео получали новые просмотры 27 ноября 2025?"
    )


@dp.message(Command("clear_file"))
async def cmd_clear_file(message: Message):
    """Обработчик команды /clear_file - очищает загруженный файл."""
    global file_analyzer
    
    if file_analyzer and file_analyzer.has_data():
        file_analyzer.clear_data()
        await message.answer(
            "✅ Загруженный файл очищен. "
            "Теперь бот будет использовать данные из базы данных."
        )
    else:
        await message.answer("ℹ️ Нет загруженного файла для очистки.")


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
                f"Ошибка при обработке запроса через file_analyzer "
                f"'{query}': {e}",
                exc_info=True
            )
            
            try:
                await processing_msg.delete()
            except Exception:
                pass
            
            error_msg = str(e)
            if ("не загружены" in error_msg.lower() or
                    "not loaded" in error_msg.lower()):
                user_message = (
                    "Данные не загружены. Пожалуйста, отправьте JSON файл."
                )
            else:
                user_message = (
                    f"Произошла ошибка при анализе данных: {error_msg}\n\n"
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
            f"Ошибка при обработке запроса '{query}': {e}",
            exc_info=True
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
        elif "подключ" in error_msg.lower() or "connection" in error_msg.lower():
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
    
    # Показываем, что бот обрабатывает файл
    processing_msg = await message.answer("📥 Загружаю и анализирую файл...")
    
    tmp_path = None
    try:
        # Скачиваем файл
        file = await bot.get_file(document.file_id)
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.json') as tmp_file:
            tmp_path = tmp_file.name
            await bot.download_file(file.file_path, tmp_path)
        
        try:
            # Загружаем JSON
            file_analyzer.load_json_file(tmp_path)
            
            # Удаляем временный файл
            os.unlink(tmp_path)
            tmp_path = None
            
            # Удаляем сообщение "Загружаю..."
            try:
                await processing_msg.delete()
            except Exception:
                pass
            
            await message.answer(
                f"✅ Файл '{document.file_name}' успешно загружен "
                f"и проанализирован!\n\n"
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
            
        except ValueError as e:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await message.answer(
                f"❌ Ошибка при обработке JSON файла: {str(e)}\n\n"
                "Убедитесь, что файл содержит корректный JSON."
            )
        except Exception as e:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            try:
                await processing_msg.delete()
            except Exception:
                pass
            raise
            
    except Exception as e:
        logger.error(f"Ошибка при загрузке файла: {e}", exc_info=True)
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(
            f"❌ Произошла ошибка при загрузке файла: {str(e)}\n\n"
            "Попробуйте отправить файл еще раз или обратитесь "
            "к администратору."
        )


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
                f"Ошибка при обработке запроса через file_analyzer "
                f"'{user_query}': {e}",
                exc_info=True
            )
            
            try:
                await processing_msg.delete()
            except Exception:
                pass
            
            error_msg = str(e)
            if ("не загружены" in error_msg.lower() or
                    "not loaded" in error_msg.lower()):
                user_message = (
                    "Данные не загружены. Пожалуйста, отправьте JSON файл."
                )
            else:
                user_message = (
                    f"Произошла ошибка при анализе данных: {error_msg}\n\n"
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
            f"Ошибка при обработке запроса '{user_query}': {e}",
            exc_info=True
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
                "Попробуйте переформулировать вопрос более конкретно, например:\n"
                "• Сколько всего видео в системе?\n"
                "• Сколько просмотров у всех видео?\n"
                "• На сколько выросли просмотры 28 ноября 2025?"
            )
        elif "подключ" in error_msg.lower() or "connection" in error_msg.lower():
            user_message = (
                "Ошибка подключения к базе данных или API.\n"
                "Пожалуйста, обратитесь к администратору."
            )
        else:
            user_message = (
                f"Произошла ошибка: {error_msg}\n\n"
                "Попробуйте переформулировать вопрос или обратитесь к администратору."
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
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
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
        logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)
