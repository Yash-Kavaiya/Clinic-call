from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


def _sqlite_connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _ensure_sqlite_dir(url: str) -> None:
    if not url.startswith("sqlite:///"):
        return
    path = url.replace("sqlite:///", "", 1)
    if path.startswith("./"):
        path = path[2:]
    db_path = Path(path)
    if not db_path.is_absolute():
        db_path = Path(__file__).resolve().parent.parent / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir(settings.database_url)

engine = create_engine(
    settings.database_url,
    connect_args=_sqlite_connect_args(settings.database_url),
    echo=False,
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=15000")
    cursor.close()


@event.listens_for(engine, "begin")
def _sqlite_immediate(conn) -> None:
    if conn.dialect.name == "sqlite":
        conn.exec_driver_sql("BEGIN IMMEDIATE")


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ping_db() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
