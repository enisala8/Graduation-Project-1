import json
import sqlite3
from contextlib import contextmanager

from app.config import settings
from app.memory import ProjectMemory
from app.schemas import Card, CardStatus, Draft, Email, ProcessedEmail

SCHEMA = """
CREATE TABLE IF NOT EXISTS project (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    email_json TEXT NOT NULL,
    result_json TEXT,
    draft_json TEXT,
    error TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    decided_at TEXT
);
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


class DuplicateEmail(Exception):
    """Bu e-posta ID'si için zaten kart var (aynı mail iki kez işlenmesin)."""


@contextmanager
def _conn():
    # Yol her çağrıda ayardan okunur; testler geçici bir dosya verebilsin diye.
    conn = sqlite3.connect(settings.database_url, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---- proje hafızası -------------------------------------------------------
def save_project(memory: ProjectMemory) -> None:
    with _conn() as conn:
        conn.execute("INSERT INTO project (data) VALUES (?)", (memory.model_dump_json(),))


def load_latest_project() -> ProjectMemory | None:
    with _conn() as conn:
        row = conn.execute("SELECT data FROM project ORDER BY id DESC LIMIT 1").fetchone()
    return ProjectMemory.model_validate_json(row["data"]) if row else None


# ---- kartlar --------------------------------------------------------------
def _to_card(row: sqlite3.Row) -> Card:
    return Card(
        id=row["id"],
        status=CardStatus(row["status"]),
        email=Email.model_validate_json(row["email_json"]),
        result=ProcessedEmail.model_validate_json(row["result_json"]) if row["result_json"] else None,
        draft=Draft.model_validate_json(row["draft_json"]) if row["draft_json"] else None,
        error=row["error"],
        created_at=row["created_at"],
        decided_at=row["decided_at"],
    )


def create_card(email: Email) -> int:
    try:
        with _conn() as conn:
            cur = conn.execute(
                "INSERT INTO cards (email_id, status, email_json) VALUES (?, ?, ?)",
                (email.id, CardStatus.PROCESSING.value, email.model_dump_json()),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError as e:
        raise DuplicateEmail(email.id) from e


def get_card(card_id: int) -> Card | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
    return _to_card(row) if row else None


def list_cards(status: CardStatus | None = None) -> list[Card]:
    with _conn() as conn:
        if status:
            rows = conn.execute("SELECT * FROM cards WHERE status = ? ORDER BY id DESC", (status.value,))
        else:
            rows = conn.execute("SELECT * FROM cards ORDER BY id DESC")
        return [_to_card(r) for r in rows.fetchall()]


def set_card_analysis(
    card_id: int, status: CardStatus, result: ProcessedEmail | None = None,
    draft: Draft | None = None, error: str | None = None,
) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE cards SET status = ?, result_json = ?, draft_json = ?, error = ? WHERE id = ?",
            (status.value, result.model_dump_json() if result else None,
             draft.model_dump_json() if draft else None, error, card_id),
        )


def transition(card_id: int, from_status: CardStatus, to_status: CardStatus, draft: Draft | None = None) -> bool:
    """Durumu yalnızca hâlâ `from_status` ise değiştirir (çift onay/yarış koşulu engellenir)."""
    decided = to_status in (CardStatus.APPROVED, CardStatus.REJECTED)
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE cards SET status = ?, decided_at = CASE WHEN ? THEN CURRENT_TIMESTAMP END, "
            "draft_json = COALESCE(?, draft_json) WHERE id = ? AND status = ?",
            (to_status.value, decided, draft.model_dump_json() if draft else None, card_id, from_status.value),
        )
        return cur.rowcount == 1


# ---- giden kutusu (mock sağlayıcının "gönderdikleri") ----------------------
def add_outbox(kind: str, payload: dict) -> None:
    with _conn() as conn:
        conn.execute("INSERT INTO outbox (kind, payload_json) VALUES (?, ?)", (kind, json.dumps(payload, ensure_ascii=False)))


def list_outbox() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT kind, payload_json, created_at FROM outbox ORDER BY id").fetchall()
    return [{"kind": r["kind"], "payload": json.loads(r["payload_json"]), "created_at": r["created_at"]} for r in rows]
