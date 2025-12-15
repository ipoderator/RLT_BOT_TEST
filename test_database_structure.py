"""
Скрипт для проверки структуры базы данных.
Проверяет наличие всех таблиц, колонок, индексов и связей.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import inspect, text
from database import get_engine

load_dotenv()


def check_database_structure():
    """Проверяет структуру базы данных."""
    
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("="*70)
        print("⚠️  DATABASE_URL не найден")
        print("="*70)
        print("\nДля проверки структуры БД необходимо настроить DATABASE_URL.")
        print("\nВарианты решения:")
        print("1. Создайте файл .env:")
        print("   python setup_env.py")
        print("\n2. Или создайте вручную:")
        print("   cp .env.example .env")
        print("   # Затем отредактируйте .env и укажите DATABASE_URL")
        print("\n3. Формат DATABASE_URL:")
        print("   postgresql://user:password@host:port/database_name")
        print("   Пример: postgresql://postgres:password@localhost:5432/video_analytics")
        print("\n" + "="*70)
        return False
    
    print("="*70)
    print("ПРОВЕРКА СТРУКТУРЫ БАЗЫ ДАННЫХ")
    print("="*70)
    
    try:
        engine = get_engine(db_url)
        inspector = inspect(engine)
        
        # Получаем список таблиц
        tables = inspector.get_table_names()
        print(f"\nНайдено таблиц: {len(tables)}")
        for table in tables:
            print(f"  - {table}")
        
        # Проверка таблицы videos
        print("\n" + "-"*70)
        print("ПРОВЕРКА ТАБЛИЦЫ 'videos'")
        print("-"*70)
        
        if 'videos' not in tables:
            print("❌ Таблица 'videos' не найдена!")
            return False
        
        print("✅ Таблица 'videos' существует")
        
        columns = inspector.get_columns('videos')
        print(f"\nКолонки ({len(columns)}):")
        required_columns = {
            'id': 'INTEGER PRIMARY KEY',
            'creator_id': 'STRING',
            'video_created_at': 'DATETIME',
            'views_count': 'INTEGER',
            'likes_count': 'INTEGER',
            'comments_count': 'INTEGER',
            'reports_count': 'INTEGER',
            'created_at': 'DATETIME',
            'updated_at': 'DATETIME'
        }
        
        column_names = [col['name'] for col in columns]
        for col_name, col_type in required_columns.items():
            if col_name in column_names:
                col_info = next(c for c in columns if c['name'] == col_name)
                print(f"  ✅ {col_name}: {col_info['type']}")
            else:
                print(f"  ❌ {col_name}: ОТСУТСТВУЕТ")
        
        # Проверка индексов videos
        indexes = inspector.get_indexes('videos')
        print(f"\nИндексы ({len(indexes)}):")
        for idx in indexes:
            print(f"  - {idx['name']}: {idx['column_names']}")
        
        # Проверка таблицы video_snapshots
        print("\n" + "-"*70)
        print("ПРОВЕРКА ТАБЛИЦЫ 'video_snapshots'")
        print("-"*70)
        
        if 'video_snapshots' not in tables:
            print("❌ Таблица 'video_snapshots' не найдена!")
            return False
        
        print("✅ Таблица 'video_snapshots' существует")
        
        columns = inspector.get_columns('video_snapshots')
        print(f"\nКолонки ({len(columns)}):")
        required_columns = {
            'id': 'INTEGER PRIMARY KEY',
            'video_id': 'INTEGER FOREIGN KEY',
            'views_count': 'INTEGER',
            'likes_count': 'INTEGER',
            'comments_count': 'INTEGER',
            'reports_count': 'INTEGER',
            'delta_views_count': 'INTEGER',
            'delta_likes_count': 'INTEGER',
            'delta_comments_count': 'INTEGER',
            'delta_reports_count': 'INTEGER',
            'created_at': 'DATETIME',
            'updated_at': 'DATETIME'
        }
        
        column_names = [col['name'] for col in columns]
        for col_name, col_type in required_columns.items():
            if col_name in column_names:
                col_info = next(c for c in columns if c['name'] == col_name)
                print(f"  ✅ {col_name}: {col_info['type']}")
            else:
                print(f"  ❌ {col_name}: ОТСУТСТВУЕТ")
        
        # Проверка индексов video_snapshots
        indexes = inspector.get_indexes('video_snapshots')
        print(f"\nИндексы ({len(indexes)}):")
        for idx in indexes:
            print(f"  - {idx['name']}: {idx['column_names']}")
        
        # Проверка составного индекса
        composite_index_found = any(
            idx['name'] == 'ix_video_snapshots_video_time' 
            for idx in indexes
        )
        if composite_index_found:
            print("  ✅ Составной индекс 'ix_video_snapshots_video_time' найден")
        else:
            print("  ⚠️  Составной индекс 'ix_video_snapshots_video_time' не найден")
        
        # Проверка внешних ключей
        print("\n" + "-"*70)
        print("ПРОВЕРКА ВНЕШНИХ КЛЮЧЕЙ")
        print("-"*70)
        
        fks = inspector.get_foreign_keys('video_snapshots')
        if fks:
            for fk in fks:
                print(f"  ✅ {fk['name']}: {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")
        else:
            print("  ⚠️  Внешние ключи не найдены (возможно, используются relationship в SQLAlchemy)")
        
        # Проверка данных
        print("\n" + "-"*70)
        print("ПРОВЕРКА ДАННЫХ")
        print("-"*70)
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM videos"))
            video_count = result.scalar()
            print(f"  Видео: {video_count}")
            
            result = conn.execute(text("SELECT COUNT(*) FROM video_snapshots"))
            snapshot_count = result.scalar()
            print(f"  Снапшотов: {snapshot_count}")
            
            if video_count > 0:
                result = conn.execute(text("SELECT COUNT(DISTINCT creator_id) FROM videos"))
                creator_count = result.scalar()
                print(f"  Уникальных креаторов: {creator_count}")
        
        print("\n" + "="*70)
        print("✅ ПРОВЕРКА ЗАВЕРШЕНА")
        print("="*70)
        
        return True
        
    except ImportError as e:
        print(f"\n❌ ОШИБКА ИМПОРТА: {e}")
        print("Убедитесь, что все зависимости установлены: pip install -r requirements.txt")
        return False
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ ОШИБКА: {error_msg}")
        
        # Более информативные сообщения для частых ошибок
        if "could not connect" in error_msg.lower() or "connection" in error_msg.lower():
            print("\n💡 Возможные причины:")
            print("   - PostgreSQL не запущен")
            print("   - Неверный DATABASE_URL")
            print("   - Неверные учетные данные")
            print("\nПроверьте:")
            print("   1. Запущен ли PostgreSQL: psql --version")
            print("   2. Правильность DATABASE_URL в .env файле")
            print("   3. Существует ли база данных")
        elif "role" in error_msg.lower() and "does not exist" in error_msg.lower():
            print("\n💡 Проблема: роль пользователя PostgreSQL не существует")
            print("\nРешения:")
            print("1. Создайте роль 'postgres':")
            print("   createuser -s postgres")
            print("\n2. Или используйте существующего пользователя в DATABASE_URL:")
            print("   Формат: postgresql://ваш_пользователь:пароль@localhost:5432/video_analytics")
            print("   Пример: postgresql://glebchurkin@localhost:5432/video_analytics")
            print("\n3. Или создайте нового пользователя:")
            print("   createuser -s ваш_пользователь")
            print("   createdb -O ваш_пользователь video_analytics")
        elif "does not exist" in error_msg.lower() or "не существует" in error_msg.lower():
            print("\n💡 Возможные причины:")
            print("   - База данных не создана")
            print("   - Неверное имя базы данных в DATABASE_URL")
            print("\nСоздайте базу данных:")
            print("   createdb video_analytics")
            print("   # или")
            print("   psql -c 'CREATE DATABASE video_analytics;'")
        else:
            # Для других ошибок показываем полный traceback
            import traceback
            print("\nПолная информация об ошибке:")
            traceback.print_exc()
        
        return False


if __name__ == "__main__":
    check_database_structure()
