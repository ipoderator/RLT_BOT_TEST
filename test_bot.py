"""
Простой тестовый скрипт для проверки работы системы без Telegram.
Проверяет все примеры вопросов из технического задания.
"""
import asyncio
import os
from dotenv import load_dotenv
from query_executor import VideoAnalytics

load_dotenv()


async def test_analytics():
    """Тестирует систему аналитики с примерами вопросов из ТЗ."""
    
    gigachat_credentials = os.getenv("GIGACHAT_CREDENTIALS")
    db_url = os.getenv("DATABASE_URL")
    
    if not gigachat_credentials:
        print("="*70)
        print("⚠️  GIGACHAT_CREDENTIALS не найден")
        print("="*70)
        print("\nДля тестирования необходимо настроить GIGACHAT_CREDENTIALS в .env файле.")
        print("\nСоздайте файл .env:")
        print("   python setup_env.py")
        print("\nИли создайте вручную:")
        print("   cp .env.example .env")
        print("   # Затем отредактируйте .env и укажите GIGACHAT_CREDENTIALS")
        print("\nПолучить ключ можно на: https://developers.sber.ru/gigachat")
        print("="*70)
        return
    
    if not db_url:
        print("="*70)
        print("⚠️  DATABASE_URL не найден")
        print("="*70)
        print("\nДля тестирования необходимо настроить DATABASE_URL в .env файле.")
        print("\nСоздайте файл .env:")
        print("   python setup_env.py")
        print("\nИли создайте вручную:")
        print("   cp .env.example .env")
        print("   # Затем отредактируйте .env и укажите DATABASE_URL")
        print("\nФормат: postgresql://user:password@host:port/database_name")
        print("="*70)
        return
    
    analytics = VideoAnalytics(db_url=db_url, gigachat_credentials=gigachat_credentials)
    
    # Все примеры вопросов из технического задания
    test_queries = [
        {
            "query": "Сколько всего видео есть в системе?",
            "description": "Пример 1: Подсчет всех видео"
        },
        {
            "query": "Сколько всего просмотров у всех видео?",
            "description": "Дополнительный: Сумма просмотров"
        },
        {
            "query": "Сколько видео набрало больше 100000 просмотров за всё время?",
            "description": "Пример 3: Видео с просмотрами > 100000"
        },
        {
            "query": "На сколько просмотров в сумме выросли все видео 28 ноября 2025?",
            "description": "Пример 4: Сумма прироста просмотров за дату"
        },
        {
            "query": "Сколько разных видео получали новые просмотры 27 ноября 2025?",
            "description": "Пример 5: Разные видео с новыми просмотрами"
        }
    ]
    
    print("="*70)
    print("ТЕСТИРОВАНИЕ СИСТЕМЫ АНАЛИТИКИ")
    print("="*70)
    print()
    
    passed = 0
    failed = 0
    
    try:
        for i, test_case in enumerate(test_queries, 1):
            query = test_case["query"]
            description = test_case.get("description", "")
            
            print(f"{i}. {description}")
            print(f"   Вопрос: {query}")
            
            try:
                answer = await analytics.answer_question(query)
                print(f"   Ответ: {answer}")
                
                # Проверка формата ответа (должно быть число)
                if answer.replace('.', '').replace('-', '').isdigit() or answer == "Данные не найдены":
                    print(f"   ✅ Формат ответа корректен (число)")
                    passed += 1
                else:
                    print(f"   ⚠️  Формат ответа некорректен: ожидается число, получено: {answer}")
                    failed += 1
                    
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
                failed += 1
            
            print()
            
    finally:
        await analytics.close()
    
    print("="*70)
    print(f"ИТОГИ: Успешно: {passed}, Ошибок: {failed}, Всего: {passed + failed}")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(test_analytics())
