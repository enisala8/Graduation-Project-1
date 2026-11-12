from datetime import date
from enum import Enum

from pydantic import BaseModel, Field

from app.memory import ImpactReport


class Category(str, Enum):
    BLOCKER = "BLOCKER"  # bir görev gecikiyor / engellenmiş
    SCOPE_CREEP = "SCOPE_CREEP"  # plan dışı yeni talep
    RESOURCE = "RESOURCE"  # kişi / ekipman / erişim eksikliği
    STATUS_UPDATE = "STATUS_UPDATE"  # bilgilendirme, aksiyon gerekmez


class Risk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ActionType(str, Enum):
    SEND_EMAIL = "SEND_EMAIL"
    SCHEDULE_MEETING = "SCHEDULE_MEETING"
    NONE = "NONE"


class Email(BaseModel):
    id: str
    sender: str
    to: list[str]
    cc: list[str] = []
    subject: str
    body: str
    date: date


class Analysis(BaseModel):
    """LLM'in döndürmesi gereken yapı. Tüm alanlar zorunlu: şema sağlayıcıya olduğu gibi gider."""

    category: Category
    risk: Risk
    confidence: float = Field(ge=0, le=1, description="0-1 arası kendi güveni")
    reasoning: str = Field(description="Kısa gerekçe (1-3 cümle)")
    related_task_id: str | None = Field(description="Planda var olan ilgili görev ID'si, yoksa null")
    delay_days: int | None = Field(ge=0, le=365, description="E-postadan çıkan gecikme (gün), yoksa null")
    action_type: ActionType
    draft_to: list[str] = Field(description="Taslağın alıcıları (e-posta adresleri), yoksa boş liste")
    draft_subject: str = Field(description="Taslak konu, aksiyon yoksa boş string")
    draft_body: str = Field(description="Taslak metin, aksiyon yoksa boş string")


class ProcessedEmail(BaseModel):
    email_id: str
    ignored_reason: str | None = None
    analysis: Analysis | None = None
    impact: ImpactReport | None = None
    warnings: list[str] = []
