import json
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import cards, db
from app.analysis import is_relevant
from app.config import settings
from app.llm import LLMClient, LLMError, get_llm_client
from app.memory import ImpactReport, ProjectFileError, ProjectMemory, load_project
from app.providers import MailProvider, MailProviderError, get_mail_provider
from app.schemas import Card, CardStatus, DraftEdit, Email

app = FastAPI(title="Chronos Agent")

# React paneli (farklı port) bu API'ye tarayıcıdan istek atabilsin diye gerekli.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEMO_MAILS = Path(__file__).resolve().parent.parent / "data" / "mails.json"


# ---- bağımlılıklar (testlerde sahte LLM/sağlayıcı ile değiştirilir) -------------
def get_llm() -> LLMClient:
    try:
        return get_llm_client()
    except LLMError as e:
        raise HTTPException(503, f"LLM yapılandırılmamış: {e}") from e


def get_provider() -> MailProvider:
    try:
        return get_mail_provider()
    except MailProviderError as e:
        raise HTTPException(503, str(e)) from e


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mail_provider": settings.mail_provider}


# ---- proje hafızası ---------------------------------------------------------
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@app.post("/project")
async def upload_project(file: UploadFile) -> ProjectMemory:
    """Proje Excel'ini yükler, doğrular ve proje hafızası olarak kaydeder."""
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(400, "Yalnızca .xlsx dosyası yüklenebilir")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Dosya 5 MB'tan büyük")
    try:
        memory = load_project(content)
    except ProjectFileError as e:
        raise HTTPException(422, {"problems": e.problems}) from e
    db.save_project(memory)
    return memory


def _current_project() -> ProjectMemory:
    memory = db.load_latest_project()
    if memory is None:
        raise HTTPException(409, "Önce proje Excel'i yüklenmeli (POST /project)")
    return memory


@app.get("/project")
def get_project() -> ProjectMemory:
    memory = db.load_latest_project()
    if memory is None:
        raise HTTPException(404, "Henüz proje Excel'i yüklenmedi")
    return memory


@app.get("/project/impact")
def project_impact(task_id: str, days: int = Query(gt=0, le=365)) -> ImpactReport:
    """Bir görev `days` gün gecikirse hangi görevler ve proje bitişi nasıl etkilenir."""
    memory = _current_project()
    try:
        return memory.delay_impact(task_id, days)
    except KeyError:
        raise HTTPException(404, f"Görev bulunamadı: {task_id}") from None


# ---- e-postalar ve kartlar -------------------------------------------------
@app.post("/emails", status_code=202)
def submit_email(email: Email, background: BackgroundTasks, llm: LLMClient = Depends(get_llm)):
    """Yeni maili alır. Analiz arka planda sürer; kart PROCESSING olarak açılır."""
    memory = _current_project()
    if not is_relevant(email, memory):
        return JSONResponse(status_code=200, content={"status": "ignored", "reason": "Gönderen/alıcılar proje planında yok"})
    try:
        card_id = db.create_card(email)
    except db.DuplicateEmail:
        raise HTTPException(409, f"Bu e-posta zaten işlendi: {email.id}") from None
    background.add_task(cards.analyze_card, card_id, memory, llm)
    return {"card_id": card_id, "status": CardStatus.PROCESSING.value}


@app.post("/demo/emails", status_code=202)
def load_demo_emails(background: BackgroundTasks, llm: LLMClient = Depends(get_llm)):
    """Geliştirme/demo: data/mails.json içindeki sahte mailleri sırayla işler."""
    memory = _current_project()
    keys = ("expected", "ignored", "injection")
    card_ids, skipped = [], 0
    for item in json.loads(DEMO_MAILS.read_text(encoding="utf-8")):
        email = Email(**{k: v for k, v in item.items() if k not in keys})
        if not is_relevant(email, memory):
            skipped += 1
            continue
        try:
            card_ids.append(db.create_card(email))
        except db.DuplicateEmail:
            skipped += 1
    background.add_task(cards.analyze_cards, card_ids, memory, llm)
    return {"queued": len(card_ids), "skipped": skipped}


@app.get("/cards")
def list_cards(status: CardStatus | None = None) -> list[Card]:
    return db.list_cards(status)


@app.get("/cards/{card_id}")
def get_card(card_id: int) -> Card:
    card = db.get_card(card_id)
    if card is None:
        raise HTTPException(404, "Kart bulunamadı")
    return card


@app.post("/cards/{card_id}/approve")
def approve_card(card_id: int, edit: DraftEdit | None = None, provider: MailProvider = Depends(get_provider)) -> Card:
    try:
        return cards.approve(card_id, edit, provider)
    except cards.CardError as e:
        raise HTTPException(e.status_code, e.detail) from e


@app.post("/cards/{card_id}/reject")
def reject_card(card_id: int) -> Card:
    try:
        return cards.reject(card_id)
    except cards.CardError as e:
        raise HTTPException(e.status_code, e.detail) from e


@app.get("/outbox")
def outbox() -> list[dict]:
    """Mock sağlayıcının 'gönderdiği' şeyler (yalnızca MAIL_PROVIDER=mock iken anlamlı)."""
    return db.list_outbox()
