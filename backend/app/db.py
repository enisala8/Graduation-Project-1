import sqlite3

from app.config import settings
from app.memory import ProjectMemory


def _connect() -> sqlite3.Connection:
    # Yol her çağrıda ayardan okunur; testler geçici bir dosya verebilsin diye.
    conn = sqlite3.connect(settings.database_url)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS project ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "data TEXT NOT NULL)"
    )
    return conn


def save_project(memory: ProjectMemory) -> None:
    with _connect() as conn:
        conn.execute("INSERT INTO project (data) VALUES (?)", (memory.model_dump_json(),))


def load_latest_project() -> ProjectMemory | None:
    with _connect() as conn:
        row = conn.execute("SELECT data FROM project ORDER BY id DESC LIMIT 1").fetchone()
    return ProjectMemory.model_validate_json(row[0]) if row else None
