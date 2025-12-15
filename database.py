"""
Модели базы данных для системы аналитики видео.
"""
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, ForeignKey, BigInteger
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()


class Video(Base):
    """Модель таблицы videos - итоговая статистика по каждому видео."""
    __tablename__ = 'videos'

    id = Column(Integer, primary_key=True)
    creator_id = Column(String, nullable=False, index=True)
    video_created_at = Column(DateTime, nullable=True)
    views_count = Column(BigInteger, default=0)
    likes_count = Column(BigInteger, default=0)
    comments_count = Column(BigInteger, default=0)
    reports_count = Column(BigInteger, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Связь с снапшотами
    snapshots = relationship(
        "VideoSnapshot", back_populates="video", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return (
            f"<Video(id={self.id}, creator_id={self.creator_id}, "
            f"views={self.views_count})>"
        )


class VideoSnapshot(Base):
    """Модель таблицы video_snapshots - почасовые снапшоты статистики."""
    __tablename__ = 'video_snapshots'

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(
        Integer,
        ForeignKey('videos.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    views_count = Column(BigInteger, default=0)
    likes_count = Column(BigInteger, default=0)
    comments_count = Column(BigInteger, default=0)
    reports_count = Column(BigInteger, default=0)
    delta_views_count = Column(BigInteger, default=0)
    delta_likes_count = Column(BigInteger, default=0)
    delta_comments_count = Column(BigInteger, default=0)
    delta_reports_count = Column(BigInteger, default=0)
    created_at = Column(DateTime, nullable=False, index=True)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Связь с видео
    video = relationship("Video", back_populates="snapshots")

    def __repr__(self):
        return (
            f"<VideoSnapshot(id={self.id}, video_id={self.video_id}, "
            f"created_at={self.created_at})>"
        )


def init_db(database_url: str):
    """
    Инициализирует базу данных, создавая все таблицы.

    Args:
        database_url: URL базы данных PostgreSQL в формате
            postgresql://user:password@host:port/dbname

    Returns:
        Engine объект SQLAlchemy
    """
    # Убираем префикс asyncpg если есть,
    # используем синхронный драйвер для миграций
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace(
            "postgresql+asyncpg://", "postgresql://", 1
        )
    elif not database_url.startswith("postgresql://"):
        database_url = f"postgresql://{database_url}"

    engine = create_engine(database_url, echo=False)

    # Создаем все таблицы
    Base.metadata.create_all(engine)

    return engine


def get_session(engine):
    """
    Создает сессию SQLAlchemy для работы с БД.

    Args:
        engine: Engine объект SQLAlchemy

    Returns:
        Session объект
    """
    Session = sessionmaker(bind=engine)
    return Session()
