from sqlalchemy import create_engine, Column, Integer, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from bot.utils.config import config
from datetime import datetime

engine = create_engine(
    config.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300
)
db_session = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()


class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)


def init_db():
    from bot.models import user, payment, subscription  # noqa
    Base.metadata.create_all(bind=engine)
    print('Database initialized successfully.')
