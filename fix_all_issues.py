"""
Скрипт для автоматического исправления всех обнаруженных проблем.
"""
import os
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv


def fix_dependencies():
    """Исправляет проблемы с зависимостями."""
    print("\n" + "="*70)
    print("ИСПРАВЛЕНИЕ ЗАВИСИМОСТЕЙ")
    print("="*70)
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "httpx>=0.27.0"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✅ httpx обновлен")
            
            # Проверка
            import httpx
            httpx_version = tuple(map(int, httpx.__version__.split('.')[:2]))
            if httpx_version >= (0, 27):
                print(f"✅ Версия httpx {httpx.__version__} совместима")
                return True
        else:
            print("❌ Ошибка при обновлении httpx")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def suggest_postgres_fix():
    """Предлагает исправление для проблемы с PostgreSQL."""
    print("\n" + "="*70)
    print("ИСПРАВЛЕНИЕ ПРОБЛЕМЫ С POSTGRESQL")
    print("="*70)
    
    if not Path('.env').exists():
        print("❌ Файл .env не найден")
        return False
    
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("❌ DATABASE_URL не настроен")
        return False
    
    print(f"\nТекущий DATABASE_URL: {db_url[:50]}...")
    
    # Пытаемся определить текущего пользователя
    current_user = os.getenv("USER") or os.getenv("USERNAME") or "postgres"
    print(f"\n💡 Обнаружен пользователь системы: {current_user}")
    
    # Предлагаем исправление
    if "postgres" in db_url and current_user != "postgres":
        print(f"\n⚠️  В DATABASE_URL указан пользователь 'postgres', но в системе используется '{current_user}'")
        print(f"\nРекомендуется обновить DATABASE_URL в .env файле:")
        
        # Извлекаем части из текущего URL
        if "@" in db_url:
            parts = db_url.split("@")
            if len(parts) == 2:
                new_url = f"postgresql://{current_user}@{parts[1]}"
                print(f"\n{new_url}")
                print(f"\nИли создайте роль postgres:")
                print(f"  createuser -s postgres")
        
        return False
    
    return True


def main():
    """Основная функция."""
    print("="*70)
    print("АВТОМАТИЧЕСКОЕ ИСПРАВЛЕНИЕ ПРОБЛЕМ")
    print("="*70)
    
    fixes_applied = []
    
    # Исправление зависимостей
    if fix_dependencies():
        fixes_applied.append("Зависимости")
    
    # Предложение исправления PostgreSQL
    suggest_postgres_fix()
    
    print("\n" + "="*70)
    if fixes_applied:
        print(f"✅ Исправлено: {', '.join(fixes_applied)}")
    else:
        print("⚠️  Автоматические исправления не применены")
    print("="*70)
    
    print("\nСледующие шаги:")
    print("1. Если была проблема с зависимостями - перезапустите тесты")
    print("2. Если была проблема с PostgreSQL - обновите DATABASE_URL в .env")
    print("3. Запустите тесты: python run_all_tests.py")


if __name__ == "__main__":
    main()
