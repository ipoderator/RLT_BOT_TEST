"""
Скрипт для исправления проблем с зависимостями.
Обновляет httpx для совместимости с openai.
"""
import subprocess
import sys


def fix_dependencies():
    """Обновляет зависимости для исправления проблем совместимости."""
    print("="*70)
    print("ИСПРАВЛЕНИЕ ЗАВИСИМОСТЕЙ")
    print("="*70)

    print("\n1. Обновление httpx для совместимости с openai...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "httpx>=0.27.0"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✅ httpx успешно обновлен")
            print(result.stdout)
        else:
            print("❌ Ошибка при обновлении httpx:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

    print("\n2. Проверка версий...")
    try:
        import httpx
        import openai
        print(f"✅ httpx версия: {httpx.__version__}")
        print(f"✅ openai версия: {openai.__version__}")

        # Проверка совместимости
        httpx_version = tuple(map(int, httpx.__version__.split('.')[:2]))
        if httpx_version >= (0, 27):
            print("✅ Версии совместимы")
            return True
        else:
            print(f"⚠️  httpx версия {httpx.__version__} может быть несовместима")
            print("   Рекомендуется версия >= 0.27.0")
            return False
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False


if __name__ == "__main__":
    success = fix_dependencies()
    if success:
        print("\n" + "="*70)
        print("✅ ЗАВИСИМОСТИ ИСПРАВЛЕНЫ")
        print("="*70)
        print("\nТеперь можно запустить тесты:")
        print("  python run_all_tests.py")
    else:
        print("\n" + "="*70)
        print("❌ НЕ УДАЛОСЬ ИСПРАВИТЬ ЗАВИСИМОСТИ")
        print("="*70)
        print("\nПопробуйте вручную:")
        print("  pip install --upgrade httpx openai")
        sys.exit(1)
