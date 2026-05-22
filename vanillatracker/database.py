import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Katalog nadrzędny (oryginalny projekt) — używany do rozwiązania
# względnej ścieżki do bazy SQLite, aby Flask korzystał z tej samej bazy.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _build_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        # Względna ścieżka sqlite (./db.sqlite3) liczona od katalogu projektu
        if url.startswith("sqlite:///./"):
            rel = url[len("sqlite:///./"):]
            return "sqlite:///" + os.path.join(PROJECT_ROOT, rel)
        return url
    host = os.getenv("DB_HOST")
    if host:
        user = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASSWORD", "")
        port = os.getenv("DB_PORT", "3306")
        name = os.getenv("DB_NAME", "vanillatracker")
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"
    return "sqlite:///" + os.path.join(PROJECT_ROOT, "db.sqlite3")


DATABASE_URL = _build_database_url()

is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}
pool_kwargs = {} if is_sqlite else {"pool_pre_ping": True, "pool_recycle": 1800}
engine = create_engine(DATABASE_URL, connect_args=connect_args, **pool_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass
