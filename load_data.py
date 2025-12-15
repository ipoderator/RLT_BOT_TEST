"""
Скрипт для загрузки данных из JSON файла в базу данных.
"""
import json
import os
import sys
from datetime import datetime
from urllib.parse import urlparse
import requests
from database import init_db, get_session, Video, VideoSnapshot


def download_json(url: str, save_path: str = None) -> str:
    """
    Скачивает JSON файл по URL и сохраняет его локально.
    
    Args:
        url: URL JSON файла
        save_path: Путь для сохранения файла (опционально)
                  Если не указан, используется имя файла из URL или 'data.json'
    
    Returns:
        Путь к сохраненному файлу
    """
    print(f"Скачивание JSON файла с {url}...")
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Определяем путь для сохранения
        if not save_path:
            # Пробуем извлечь имя файла из URL
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            if not filename or not filename.endswith('.json'):
                filename = 'data.json'
            save_path = filename
        
        # Сохраняем файл
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        print(f"Файл успешно скачан и сохранен как {save_path}")
        return save_path
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Ошибка при скачивании файла: {e}")


def parse_datetime(date_str: str) -> datetime:
    """Парсит строку с датой в объект datetime."""
    if not date_str:
        return datetime.utcnow()
    
    # Убираем timezone информацию для упрощения парсинга
    date_str_clean = date_str.split('+')[0].split('Z')[0]
    
    # Пробуем разные форматы
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str_clean, fmt)
        except ValueError:
            continue
    
    # Если ничего не подошло, возвращаем текущее время
    print(f"Warning: Could not parse date '{date_str}', using current time")
    return datetime.utcnow()


def load_json_to_db(json_path: str, db_url: str = None):
    """
    Загружает данные из JSON файла в базу данных.
    
    Ожидаемый формат JSON - массив объектов videos:
    [
        {
            "id": 1,
            "creator_id": "...",
            "video_created_at": "...",
            "views_count": 100,
            "likes_count": 10,
            "comments_count": 5,
            "reports_count": 2,
            "created_at": "...",
            "updated_at": "...",
            "snapshots": [
                {
                    "id": 1,
                    "views_count": 50,
                    "likes_count": 5,
                    "comments_count": 2,
                    "reports_count": 1,
                    "delta_views_count": 10,
                    "delta_likes_count": 1,
                    "delta_comments_count": 0,
                    "delta_reports_count": 0,
                    "created_at": "...",
                    "updated_at": "..."
                },
                ...
            ]
        },
        ...
    ]
    """
    print(f"Loading data from {json_path}...")
    
    # Читаем JSON файл
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Файл {json_path} не найден")
    except json.JSONDecodeError as e:
        raise ValueError(f"Ошибка при парсинге JSON: {e}")
    
    # Если данные в формате объекта, извлекаем массив
    if isinstance(data, dict):
        if 'videos' in data:
            data = data['videos']
        elif 'data' in data:
            data = data['data']
        else:
            raise ValueError("JSON должен быть массивом или объектом с ключом 'videos' или 'data'")
    
    if not isinstance(data, list):
        raise ValueError("Данные должны быть массивом видео")
    
    # Инициализируем БД
    import os
    if not db_url:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError(
                "DATABASE_URL не указан. Укажите URL базы данных PostgreSQL "
                "или установите переменную окружения DATABASE_URL"
            )
    
    # Для синхронной загрузки используем синхронный драйвер
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif not db_url.startswith("postgresql://"):
        db_url = f"postgresql://{db_url}"
    
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        loaded_videos = 0
        loaded_snapshots = 0
        
        for video_data in data:
            # Получаем ID видео из данных
            video_id = video_data.get('id')
            if not video_id:
                print("Warning: Video without id, skipping...")
                continue
            
            # Проверяем, существует ли уже такое видео
            video = session.query(Video).filter_by(id=video_id).first()
            
            video_created_at = None
            if video_data.get('video_created_at'):
                video_created_at = parse_datetime(video_data['video_created_at'])
            
            created_at = None
            if video_data.get('created_at'):
                created_at = parse_datetime(video_data['created_at'])
            
            updated_at = None
            if video_data.get('updated_at'):
                updated_at = parse_datetime(video_data['updated_at'])
            
            if video:
                # Обновляем существующее видео
                video.creator_id = video_data.get('creator_id', video.creator_id)
                if video_created_at:
                    video.video_created_at = video_created_at
                video.views_count = video_data.get('views_count', 0)
                video.likes_count = video_data.get('likes_count', 0)
                video.comments_count = video_data.get('comments_count', 0)
                video.reports_count = video_data.get('reports_count', 0)
                if updated_at:
                    video.updated_at = updated_at
            else:
                # Создаем новое видео
                video = Video(
                    id=video_id,
                    creator_id=video_data.get('creator_id', ''),
                    video_created_at=video_created_at,
                    views_count=video_data.get('views_count', 0),
                    likes_count=video_data.get('likes_count', 0),
                    comments_count=video_data.get('comments_count', 0),
                    reports_count=video_data.get('reports_count', 0),
                    created_at=created_at,
                    updated_at=updated_at,
                )
                session.add(video)
            
            # Загружаем снапшоты
            snapshots = video_data.get('snapshots', [])
            for snapshot_data in snapshots:
                snapshot_id = snapshot_data.get('id')
                snapshot_created_at = None
                if snapshot_data.get('created_at'):
                    snapshot_created_at = parse_datetime(snapshot_data['created_at'])
                else:
                    print("Warning: Snapshot without created_at, skipping...")
                    continue
                
                snapshot_updated_at = None
                if snapshot_data.get('updated_at'):
                    snapshot_updated_at = parse_datetime(snapshot_data['updated_at'])
                
                # Проверяем, существует ли уже такой снапшот
                existing = None
                if snapshot_id:
                    existing = session.query(VideoSnapshot).filter_by(id=snapshot_id).first()
                else:
                    # Если нет ID, проверяем по video_id и created_at
                    existing = session.query(VideoSnapshot).filter_by(
                        video_id=video.id,
                        created_at=snapshot_created_at
                    ).first()
                
                if not existing:
                    # Создаем новый снапшот
                    snapshot_kwargs = {
                        'video_id': video.id,
                        'views_count': snapshot_data.get('views_count', 0),
                        'likes_count': snapshot_data.get('likes_count', 0),
                        'comments_count': snapshot_data.get('comments_count', 0),
                        'reports_count': snapshot_data.get('reports_count', 0),
                        'delta_views_count': snapshot_data.get('delta_views_count', 0),
                        'delta_likes_count': snapshot_data.get('delta_likes_count', 0),
                        'delta_comments_count': snapshot_data.get('delta_comments_count', 0),
                        'delta_reports_count': snapshot_data.get('delta_reports_count', 0),
                        'created_at': snapshot_created_at,
                    }
                    
                    # Добавляем ID только если он есть
                    if snapshot_id:
                        snapshot_kwargs['id'] = snapshot_id
                    if snapshot_updated_at:
                        snapshot_kwargs['updated_at'] = snapshot_updated_at
                    
                    snapshot = VideoSnapshot(**snapshot_kwargs)
                    session.add(snapshot)
                    loaded_snapshots += 1
            
            loaded_videos += 1
        
        session.commit()
        print(f"Successfully loaded {loaded_videos} videos and {loaded_snapshots} snapshots")
        
    except Exception as e:
        session.rollback()
        print(f"Error loading data: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python load_data.py <path_to_json_file_or_url>")
        print("Примеры:")
        print("  python load_data.py data.json")
        print("  python load_data.py https://example.com/data.json")
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    # Проверяем, является ли входной путь URL
    if input_path.startswith(('http://', 'https://')):
        # Скачиваем файл
        json_path = download_json(input_path)
    else:
        # Используем локальный файл
        json_path = input_path
        if not os.path.exists(json_path):
            print(f"Ошибка: файл {json_path} не найден")
            sys.exit(1)
    
    # Загружаем данные в БД
    load_json_to_db(json_path)

