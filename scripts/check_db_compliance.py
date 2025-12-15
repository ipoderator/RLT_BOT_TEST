"""
Скрипт для проверки соответствия структуры базы данных техническому заданию.
"""
import os
import sys
from pathlib import Path
from sqlalchemy import inspect

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database import init_db  # noqa: E402


def check_table_structure(engine, table_name, expected_columns):
    """
    Проверяет структуру таблицы на соответствие ожидаемым колонкам.

    Args:
        engine: SQLAlchemy engine
        table_name: Имя таблицы
        expected_columns: Словарь с ожидаемыми колонками {имя: тип}

    Returns:
        tuple: (соответствует: bool, детали: dict)
    """
    inspector = inspect(engine)

    if not inspector.has_table(table_name):
        return False, {"error": f"Таблица {table_name} не существует"}

    columns = inspector.get_columns(table_name)
    actual_columns = {col['name']: str(col['type']) for col in columns}

    missing = []
    extra = []
    type_mismatches = []

    # Проверяем наличие всех ожидаемых колонок
    for col_name, expected_type in expected_columns.items():
        if col_name not in actual_columns:
            missing.append(col_name)
        else:
            actual_type = actual_columns[col_name]
            # Проверяем тип (упрощенная проверка)
            if expected_type.lower() not in actual_type.lower():
                type_mismatches.append({
                    'column': col_name,
                    'expected': expected_type,
                    'actual': actual_type
                })

    # Проверяем лишние колонки (не критично, но стоит отметить)
    for col_name in actual_columns:
        if col_name not in expected_columns:
            extra.append(col_name)

    is_compliant = len(missing) == 0 and len(type_mismatches) == 0

    return is_compliant, {
        'missing': missing,
        'extra': extra,
        'type_mismatches': type_mismatches,
        'actual_columns': actual_columns
    }


def main():
    """Основная функция проверки."""
    print("=" * 60)
    print("Проверка соответствия БД техническому заданию")
    print("=" * 60)

    # Получаем URL базы данных
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Ошибка: DATABASE_URL не установлен")
        print("Установите переменную окружения DATABASE_URL")
        sys.exit(1)

    # Инициализируем подключение
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif not db_url.startswith("postgresql://"):
        db_url = f"postgresql://{db_url}"

    try:
        engine = init_db(db_url)
        print("\n✓ Подключение к БД установлено")
    except Exception as e:
        print(f"\n✗ Ошибка подключения к БД: {e}")
        sys.exit(1)

    # Ожидаемая структура таблицы videos согласно ТЗ
    expected_videos = {
        'id': 'INTEGER',
        'creator_id': 'STRING',
        'video_created_at': 'DATETIME',
        'views_count': 'BIGINT',
        'likes_count': 'BIGINT',
        'comments_count': 'BIGINT',
        'reports_count': 'BIGINT',
        'created_at': 'DATETIME',
        'updated_at': 'DATETIME'
    }

    # Ожидаемая структура таблицы video_snapshots согласно ТЗ
    expected_snapshots = {
        'id': 'INTEGER',
        'video_id': 'INTEGER',
        'views_count': 'BIGINT',
        'likes_count': 'BIGINT',
        'comments_count': 'BIGINT',
        'reports_count': 'BIGINT',
        'delta_views_count': 'BIGINT',
        'delta_likes_count': 'BIGINT',
        'delta_comments_count': 'BIGINT',
        'delta_reports_count': 'BIGINT',
        'created_at': 'DATETIME',
        'updated_at': 'DATETIME'
    }

    print("\n" + "=" * 60)
    print("Проверка таблицы videos")
    print("=" * 60)

    is_compliant_videos, details_videos = check_table_structure(
        engine, 'videos', expected_videos
    )

    if is_compliant_videos:
        print("✓ Таблица videos соответствует ТЗ")
        print(f"  Найдено колонок: {len(details_videos['actual_columns'])}")
        for col_name in sorted(details_videos['actual_columns'].keys()):
            col_type = details_videos['actual_columns'][col_name]
            print(f"    - {col_name}: {col_type}")
    else:
        print("✗ Таблица videos НЕ соответствует ТЗ")
        if details_videos.get('missing'):
            missing_cols = ', '.join(details_videos['missing'])
            print(f"  Отсутствующие колонки: {missing_cols}")
        if details_videos.get('type_mismatches'):
            print("  Несоответствия типов:")
            for mismatch in details_videos['type_mismatches']:
                col_name = mismatch['column']
                expected = mismatch['expected']
                actual = mismatch['actual']
                print(f"    - {col_name}: ожидается {expected}, "
                      f"фактически {actual}")
        if details_videos.get('extra'):
            extra_cols = ', '.join(details_videos['extra'])
            print(f"  Дополнительные колонки (не критично): {extra_cols}")

    print("\n" + "=" * 60)
    print("Проверка таблицы video_snapshots")
    print("=" * 60)

    is_compliant_snapshots, details_snapshots = check_table_structure(
        engine, 'video_snapshots', expected_snapshots
    )

    if is_compliant_snapshots:
        print("✓ Таблица video_snapshots соответствует ТЗ")
        print(f"  Найдено колонок: {len(details_snapshots['actual_columns'])}")
        for col_name in sorted(details_snapshots['actual_columns'].keys()):
            col_type = details_snapshots['actual_columns'][col_name]
            print(f"    - {col_name}: {col_type}")
    else:
        print("✗ Таблица video_snapshots НЕ соответствует ТЗ")
        if details_snapshots.get('missing'):
            missing_cols = ', '.join(details_snapshots['missing'])
            print(f"  Отсутствующие колонки: {missing_cols}")
        if details_snapshots.get('type_mismatches'):
            print("  Несоответствия типов:")
            for mismatch in details_snapshots['type_mismatches']:
                col_name = mismatch['column']
                expected = mismatch['expected']
                actual = mismatch['actual']
                print(f"    - {col_name}: ожидается {expected}, "
                      f"фактически {actual}")
        if details_snapshots.get('extra'):
            extra_cols = ', '.join(details_snapshots['extra'])
            print(f"  Дополнительные колонки (не критично): {extra_cols}")

    # Проверка внешних ключей
    print("\n" + "=" * 60)
    print("Проверка связей между таблицами")
    print("=" * 60)

    inspector = inspect(engine)
    foreign_keys = inspector.get_foreign_keys('video_snapshots')

    video_id_fk_found = False
    for fk in foreign_keys:
        if fk['constrained_columns'] == ['video_id'] and \
           fk['referred_table'] == 'videos' and \
           'id' in fk['referred_columns']:
            video_id_fk_found = True
            msg = "✓ Внешний ключ video_snapshots.video_id -> videos.id найден"
            print(msg)
            break

    if not video_id_fk_found:
        print("✗ Внешний ключ video_snapshots.video_id -> videos.id не найден")

    # Итоговый результат
    print("\n" + "=" * 60)
    print("ИТОГОВЫЙ РЕЗУЛЬТАТ")
    print("=" * 60)

    if is_compliant_videos and is_compliant_snapshots and video_id_fk_found:
        print("✓ База данных полностью соответствует техническому заданию!")
        return 0
    else:
        print("✗ База данных не полностью соответствует техническому заданию")
        print("\nДетали:")
        if not is_compliant_videos:
            print("  - Таблица videos имеет проблемы")
        if not is_compliant_snapshots:
            print("  - Таблица video_snapshots имеет проблемы")
        if not video_id_fk_found:
            print("  - Отсутствует внешний ключ между таблицами")
        return 1


if __name__ == "__main__":
    sys.exit(main())
