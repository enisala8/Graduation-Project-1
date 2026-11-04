from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.config import settings
from app.memory import ImpactReport, ProjectFileError, ProjectMemory, load_project

app = FastAPI(title="Chronos Agent")

# React paneli (farklı port) bu API'ye tarayıcıdan istek atabilsin diye gerekli.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mail_provider": settings.mail_provider}


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
        raise HTTPException(404, "Henüz proje Excel'i yüklenmedi")
    return memory


@app.get("/project")
def get_project() -> ProjectMemory:
    return _current_project()


@app.get("/project/impact")
def project_impact(task_id: str, days: int = Query(gt=0, le=365)) -> ImpactReport:
    """Bir görev `days` gün gecikirse hangi görevler ve proje bitişi nasıl etkilenir."""
    memory = _current_project()
    try:
        return memory.delay_impact(task_id, days)
    except KeyError:
        raise HTTPException(404, f"Görev bulunamadı: {task_id}") from None
