"""
Модуль работы с базой данных PostgreSQL.
Если БД недоступна (например, при запуске без сервера), приложение продолжит работать,
просто не будет сохранять историю.
"""

import logging
import os
from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

log = logging.getLogger("rus_corrector")

# Получаем настройки из переменных окружения (с дефолтными значениями)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "rus_corrector")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

Base = declarative_base()


class CheckHistory(Base):
    """Таблица для хранения истории проверок."""
    __tablename__ = "check_history"

    id = Column(Integer, primary_key=True, index=True)
    original_text = Column(Text, nullable=False)
    corrected_text = Column(Text, nullable=False)
    errors_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


# Флаг доступности БД
db_available = False
engine = None
SessionLocal = None

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"connect_timeout": 3})
    # Пробуем подключиться и создать таблицы
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_available = True
    log.info("Подключение к PostgreSQL успешно установлено.")
except Exception as exc:
    log.warning("PostgreSQL недоступен (%s). История проверок не будет сохраняться.", exc)
    db_available = False


def save_history(original: str, corrected: str, errors_count: int) -> bool:
    """
    Сохраняет результат проверки в базу данных.
    Возвращает True, если запись прошла успешно.
    """
    if not db_available or not SessionLocal:
        return False
    try:
        db = SessionLocal()
        record = CheckHistory(
            original_text=original,
            corrected_text=corrected,
            errors_count=errors_count,
        )
        db.add(record)
        db.commit()
        db.close()
        return True
    except Exception as exc:
        log.error("Ошибка записи в БД: %s", exc)
        return False