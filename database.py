import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _database_url() -> str:
    """
    Local:  DATABASE_URL set nahi to SQLite file (utility_tracker.db) use hoti hai.
    Vercel: DATABASE_URL (Postgres, e.g. Neon) zaroori hai, kyunke Vercel par
            file system permanent nahi hota aur SQLite data kho jata hai.
    """
    url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or ""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    if not url:
        if os.getenv("VERCEL"):
            raise RuntimeError(
                "DATABASE_URL set nahi hai. Vercel > Project > Settings > Environment Variables "
                "me Postgres (Neon) ka connection string DATABASE_URL naam se add karo."
            )
        url = "sqlite:///./utility_tracker.db"
    return url


SQLALCHEMY_DATABASE_URL = _database_url()

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, pool_recycle=300)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
