"""
Скрипт для детальной проверки генерации SQL запросов.
Проверяет корректность SQL, генерируемого для различных типов запросов.
"""
import asyncio
import os
import re
from dotenv import load_dotenv
from query_generator import SQLQueryGenerator
from query_executor import VideoAnalytics

load_dotenv()


async def test_sql_generation():
    """Тестирует генерацию SQL для различных типов запросов."""
    
    gigachat_credentials = os.getenv("GIGACHAT_CREDENTIALS")
    gigachat_scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    db_url = os.getenv("DATABASE_URL")
    
    if not gigachat_credentials:
        print("="*70)
        print("⚠️  GIGACHAT_CREDENTIALS не найден")
        print("="*70)
        print("\nДля проверки генерации SQL необходимо настроить GIGACHAT_CREDENTIALS.")
        print("\nСоздайте файл .env: python setup_env.py")
        print("Получить ключ: https://developers.sber.ru/gigachat")
        print("="*70)
        return
    
    if not db_url:
        print("="*70)
        print("⚠️  DATABASE_URL не найден")
        print("="*70)
        print("\nДля проверки генерации SQL необходимо настроить DATABASE_URL.")
        print("\nСоздайте файл .env: python setup_env.py")
        print("Формат: postgresql://user:password@host:port/database_name")
        print("="*70)
        return
    
    generator = SQLQueryGenerator(credentials=gigachat_credentials, scope=gigachat_scope)
    analytics = VideoAnalytics(db_url=db_url, gigachat_credentials=gigachat_credentials, gigachat_scope=gigachat_scope)
    
    test_cases = [
        {
            "name": "Подсчет всех видео",
            "query": "Сколько всего видео есть в системе?",
            "expected_patterns": [
                r"SELECT\s+COUNT\s*\(\s*\*\s*\)\s+FROM\s+videos",
                r"COUNT\s*\(\s*\*\s*\)",
                r"FROM\s+videos"
            ],
            "should_contain": ["videos"],
            "should_not_contain": ["video_snapshots"]
        },
        {
            "name": "Видео креатора за период",
            "query": "Сколько видео у креатора с id creator123 вышло с 1 ноября 2025 по 5 ноября 2025 включительно?",
            "expected_patterns": [
                r"creator_id\s*=\s*['\"]creator123['\"]",
                r"video_created_at.*BETWEEN",
                r"2025-11-01.*2025-11-05",
                r"FROM\s+videos"
            ],
            "should_contain": ["videos", "creator_id", "2025-11"],
            "should_not_contain": ["video_snapshots"]
        },
        {
            "name": "Видео с просмотрами > 100000",
            "query": "Сколько видео набрало больше 100000 просмотров за всё время?",
            "expected_patterns": [
                r"views_count\s*>\s*100000",
                r"COUNT\s*\(\s*\*\s*\)",
                r"FROM\s+videos"
            ],
            "should_contain": ["videos", "views_count", "100000"],
            "should_not_contain": ["video_snapshots"]
        },
        {
            "name": "Сумма прироста просмотров за дату",
            "query": "На сколько просмотров в сумме выросли все видео 28 ноября 2025?",
            "expected_patterns": [
                r"SUM\s*\(\s*delta_views_count\s*\)",
                r"FROM\s+video_snapshots",
                r"2025-11-28",
                r"DATE\s*\(\s*created_at\s*\)"
            ],
            "should_contain": ["video_snapshots", "delta_views_count", "2025-11-28"],
            "should_not_contain": ["videos"]
        },
        {
            "name": "Разные видео с новыми просмотрами",
            "query": "Сколько разных видео получали новые просмотры 27 ноября 2025?",
            "expected_patterns": [
                r"COUNT\s*\(\s*DISTINCT\s+video_id\s*\)",
                r"FROM\s+video_snapshots",
                r"delta_views_count\s*>\s*0",
                r"2025-11-27"
            ],
            "should_contain": ["video_snapshots", "DISTINCT", "video_id", "delta_views_count", "2025-11-27"],
            "should_not_contain": ["videos"]
        }
    ]
    
    print("="*70)
    print("ПРОВЕРКА ГЕНЕРАЦИИ SQL ЗАПРОСОВ")
    print("="*70)
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print(f"   Запрос: {test_case['query']}")
        
        try:
            # Генерируем SQL
            sql = await generator.generate_sql(test_case['query'])
            print(f"   Сгенерированный SQL: {sql}")
            
            # Проверка паттернов
            patterns_match = True
            for pattern in test_case['expected_patterns']:
                if not re.search(pattern, sql, re.IGNORECASE):
                    print(f"   ❌ Паттерн не найден: {pattern}")
                    patterns_match = False
                else:
                    print(f"   ✅ Паттерн найден: {pattern}")
            
            # Проверка обязательных элементов
            contains_all = True
            for item in test_case['should_contain']:
                if item.lower() not in sql.lower():
                    print(f"   ❌ Должно содержать: {item}")
                    contains_all = False
            
            # Проверка отсутствия элементов
            not_contains_all = True
            for item in test_case['should_not_contain']:
                if item.lower() in sql.lower():
                    print(f"   ❌ Не должно содержать: {item}")
                    not_contains_all = False
            
            # Проверка валидации (базовая проверка на SELECT)
            is_valid = sql.upper().strip().startswith('SELECT')
            if not is_valid:
                print("   ❌ SQL не начинается с SELECT")
            
            # Проверка выполнения
            try:
                answer = await analytics.answer_question(test_case['query'])
                print(f"   Ответ: {answer}")
                
                # Проверка формата ответа
                if not (answer.replace('.', '').replace('-', '').isdigit() or answer == "Данные не найдены"):
                    print("   ⚠️  Формат ответа некорректен")
            except Exception as e:
                print(f"   ⚠️  Ошибка выполнения: {e}")
                answer_format_ok = False
            
            # Итоговая оценка
            if patterns_match and contains_all and not_contains_all:
                print("   ✅ ТЕСТ ПРОЙДЕН")
                passed += 1
            else:
                print("   ❌ ТЕСТ НЕ ПРОЙДЕН")
                failed += 1
                
        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")
            failed += 1
    
    print("\n" + "="*70)
    print(f"ИТОГИ: Пройдено: {passed}, Не пройдено: {failed}, Всего: {passed + failed}")
    print("="*70)
    
    await analytics.close()


if __name__ == "__main__":
    asyncio.run(test_sql_generation())
