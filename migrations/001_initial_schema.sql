-- Миграция 001: Создание начальной схемы базы данных
-- Создает таблицы videos и video_snapshots для системы аналитики видео

-- Таблица videos: итоговая статистика по каждому видео
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY,
    creator_id VARCHAR NOT NULL,
    video_created_at TIMESTAMP,
    views_count BIGINT DEFAULT 0,
    likes_count BIGINT DEFAULT 0,
    comments_count BIGINT DEFAULT 0,
    reports_count BIGINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индекс на creator_id для быстрого поиска по креатору
CREATE INDEX IF NOT EXISTS ix_videos_creator_id ON videos(creator_id);

-- Таблица video_snapshots: почасовые снапшоты статистики для отслеживания динамики
CREATE TABLE IF NOT EXISTS video_snapshots (
    id SERIAL PRIMARY KEY,
    video_id INTEGER NOT NULL,
    views_count BIGINT DEFAULT 0,
    likes_count BIGINT DEFAULT 0,
    comments_count BIGINT DEFAULT 0,
    reports_count BIGINT DEFAULT 0,
    delta_views_count BIGINT DEFAULT 0,
    delta_likes_count BIGINT DEFAULT 0,
    delta_comments_count BIGINT DEFAULT 0,
    delta_reports_count BIGINT DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_video_snapshots_video_id
        FOREIGN KEY (video_id)
        REFERENCES videos(id)
        ON DELETE CASCADE
);

-- Индекс на video_id для быстрого поиска снапшотов по видео
CREATE INDEX IF NOT EXISTS ix_video_snapshots_video_id ON video_snapshots(video_id);

-- Индекс на created_at для быстрого поиска снапшотов по дате
CREATE INDEX IF NOT EXISTS ix_video_snapshots_created_at ON video_snapshots(created_at);

-- Составной индекс для оптимизации запросов по видео и дате
CREATE INDEX IF NOT EXISTS ix_video_snapshots_video_id_created_at
    ON video_snapshots(video_id, created_at);

