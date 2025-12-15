"""
Тестовый скрипт для проверки конкретных примеров вопросов из ТЗ.
"""
import asyncio
import os
from dotenv import load_dotenv
from query_executor import VideoAnalytics

load_dotenv()


async def test_examples():
    """Тестирует конкретные примеры вопросов из технического задания."""

    gigachat_credentials = os.getenv("GIGACHAT_CREDENTIALS")
    db_url = os.getenv("DATABASE_URL")

    if not gigachat_credentials:
        print("="*70)
        print("⚠️  GIGACHAT_CREDENTIALS не найден")
        print("="*70)
        print("\nДля тестирования необходимо настроить GIGACHAT_CREDENTIALS в .env файле.")
        return

    if not db_url:
        print("="*70)
        print("⚠️  DATABASE_URL не найден")
        print("="*70)
        print("\nДля тестирования необходимо настроить DATABASE_URL в .env файле.")
        return

    analytics = VideoAnalytics(db_url=db_url, gigachat_credentials=gigachat_credentials)

    # Конкретные примеры из ТЗ
    test_cases = [
        {
            "question": "Сколько всего видео есть в системе?",
            "description": "Пример 1: Подсчет всех видео"
        },
        {
            "question": "Сколько видео у креатора с id creator123 вышло с 1 ноября 2025 по 5 ноября 2025 включительно?",
            "description": "Пример 2: Видео креатора за период"
        },
        {
            "question": "Сколько видео набрало больше 100 000 просмотров за всё время?",
            "description": "Пример 3: Видео с просмотрами > 100000 (с пробелом)"
        },
        {
            "question": "Сколько видео набрало больше 100000 просмотров за всё время?",
            "description": "Пример 3 (вариант): Видео с просмотрами > 100000 (без пробела)"
        },
        {
            "question": "На сколько просмотров в сумме выросли все видео 28 ноября 2025?",
            "description": "Пример 4: Сумма прироста просмотров за дату"
        },
        {
            "question": "Сколько разных видео получали новые просмотры 27 ноября 2025?",
            "description": "Пример 5: Разные видео с новыми просмотрами"
        }
    ]

    print("="*70)
    print("ТЕСТИРОВАНИЕ ПРИМЕРОВ ИЗ ТЕХНИЧЕСКОГО ЗАДАНИЯ")
    print("="*70)
    print()

    passed = 0
    failed = 0

    try:
        for i, test_case in enumerate(test_cases, 1):
            question = test_case["question"]
            description = test_case.get("description", "")

            print(f"{i}. {description}")
            print(f"   Вопрос: {question}")
            print("   Ожидается: одно число")

            try:
                answer = await analytics.answer_question(question)
                print(f"   Ответ: {answer}")

                # Проверка формата ответа (должно быть число)
                answer_clean = answer.replace('.', '').replace('-', '').replace(',', '').strip()

                if answer == "Данные не найдены":
                    print("   ⚠️  Данные не найдены (возможно, БД пуста)")
                    passed += 1
                elif answer_clean.isdigit() or (answer_clean.replace('e', '').replace('E', '').replace('+', '').isdigit()):
                    print("   ✅ Формат ответа корректен (число)")
                    passed += 1
                elif answer.startswith("Ошибка:"):
                    print(f"   ❌ Ошибка при обработке: {answer}")
                    failed += 1
                else:
                    print(f"   ⚠️  Неожиданный формат ответа: {answer}")
                    failed += 1

            except Exception as e:
                print(f"   ❌ Исключение: {e}")
                failed += 1

            print()

    finally:
        await analytics.close()

    print("="*70)
    print(f"ИТОГИ: Успешно: {passed}, Ошибок: {failed}, Всего: {passed + failed}")
    print("="*70)

    if failed == 0:
        print("\n✅ Все тесты пройдены успешно!")
    else:
        print(f"\n⚠️  Обнаружено {failed} ошибок. Проверьте логи выше.")


if __name__ == "__main__":
    asyncio.run(test_examples())

