"""
Скрипт-помощник для настройки файла .env
"""
import re
from pathlib import Path


def setup_env():
    """Создает .env файл на основе .env.example с интерактивным вводом."""

    env_example_path = Path('.env.example')
    env_path = Path('.env')

    if not env_example_path.exists():
        print("❌ Файл .env.example не найден!")
        return False

    if env_path.exists():
        response = input("⚠️  Файл .env уже существует. Перезаписать? (y/N): ")
        if response.lower() != 'y':
            print("Отменено.")
            return False

    print("\n" + "="*70)
    print("НАСТРОЙКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ")
    print("="*70)
    print("\nВведите значения для переменных окружения.")
    print("Можно нажать Enter, чтобы пропустить и заполнить позже.\n")

    # Читаем шаблон
    with open(env_example_path, 'r', encoding='utf-8') as f:
        template = f.read()

    # Запрашиваем значения
    values = {}

    print("1. TELEGRAM_BOT_TOKEN")
    print("   Получить можно у @BotFather в Telegram")
    values['TELEGRAM_BOT_TOKEN'] = input("   Введите токен бота: ").strip()

    print("\n2. OPENAI_API_KEY")
    print("   Получить можно на https://platform.openai.com/api-keys")
    values['OPENAI_API_KEY'] = input("   Введите API ключ OpenAI: ").strip()

    print("\n3. DATABASE_URL")
    print("   Формат: postgresql://user:password@host:port/dbname")
    print("   Пример: postgresql://postgres:password@localhost:5432/video_analytics")
    db_url = input("   Введите URL базы данных: ").strip()
    if db_url:
        values['DATABASE_URL'] = db_url
    else:
        # Предлагаем значения по умолчанию
        db_user = input("   Пользователь БД [postgres]: ").strip() or "postgres"
        db_password = input("   Пароль БД: ").strip()
        db_host = input("   Хост [localhost]: ").strip() or "localhost"
        db_port = input("   Порт [5432]: ").strip() or "5432"
        db_name = input("   Имя БД [video_analytics]: ").strip() or "video_analytics"

        if db_password:
            values['DATABASE_URL'] = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        else:
            values['DATABASE_URL'] = f"postgresql://{db_user}@{db_host}:{db_port}/{db_name}"

    # Заменяем значения в шаблоне
    result = template
    for key, value in values.items():
        if value:
            # Заменяем значение после знака =
            pattern = rf"^{key}=.*$"
            replacement = f"{key}={value}"
            result = re.sub(pattern, replacement, result, flags=re.MULTILINE)

    # Сохраняем .env файл
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(result)

    print("\n" + "="*70)
    print("✅ Файл .env создан!")
    print("="*70)

    # Проверяем заполненность
    filled = sum(1 for v in values.values() if v)
    total = len(values)

    if filled == total:
        print("\n✅ Все переменные заполнены.")
    else:
        print(f"\n⚠️  Заполнено {filled} из {total} переменных.")
        print("   Вы можете отредактировать файл .env вручную позже.")

    return True


if __name__ == "__main__":
    try:
        setup_env()
    except KeyboardInterrupt:
        print("\n\nОтменено пользователем.")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
