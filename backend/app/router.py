"""Router: LLM'in önerisini, yöneticiye gösterilebilecek güvenli bir taslağa çevirir.

LLM çıktısına güvenmiyoruz: alıcılar burada yeniden doğrulanır. Mail içine gömülü bir
saldırı LLM'i kandırsa bile taslak, tanımadığı bir adrese gidemez.
"""
import re

from app.config import settings
from app.memory import ProjectMemory
from app.schemas import ActionType, Analysis, Category, Draft, Email

MAX_RECIPIENTS = 10
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(addr: str) -> bool:
    return bool(EMAIL_RE.match(addr))


def allowed_recipients(email: Email, memory: ProjectMemory) -> set[str]:
    """Planda geçen adresler + bu mail zincirindeki adresler."""
    thread = {email.sender.lower(), *(a.lower() for a in email.to), *(a.lower() for a in email.cc)}
    return memory.participants() | thread


def build_draft(analysis: Analysis, email: Email, memory: ProjectMemory) -> Draft | None:
    """Aksiyon gerekmiyorsa None, gerekiyorsa temizlenmiş taslak döner."""
    # Kural: bilgilendirme maillerinden aksiyon çıkmaz (LLM ne derse desin).
    if analysis.category == Category.STATUS_UPDATE or analysis.action_type == ActionType.NONE:
        return None

    allowed = allowed_recipients(email, memory)
    manager = settings.manager_email.strip().lower()
    warnings: list[str] = []
    to: list[str] = []
    for addr in (a.strip().lower() for a in analysis.draft_to):
        if addr in to or (manager and addr == manager):
            continue  # yinelenen adres ve yöneticinin kendisi (taslağı o gönderiyor)
        if addr in allowed:
            to.append(addr)
        else:
            warnings.append(f"Bilinmeyen alıcı çıkarıldı: {addr}")
    if len(to) > MAX_RECIPIENTS:
        warnings.append(f"Alıcılar {MAX_RECIPIENTS} ile sınırlandı ({len(to)} vardı)")
        to = to[:MAX_RECIPIENTS]
    if not to:
        sender = email.sender.lower()
        if sender in memory.participants():
            to = [sender]
            warnings.append("Alıcı belirtilmediği için gönderen eklendi")
        else:
            warnings.append("Alıcı belirlenemedi; onaylamadan önce alıcı ekleyin")

    return Draft(
        action_type=analysis.action_type, to=to,
        subject=analysis.draft_subject.strip(), body=analysis.draft_body.strip(), warnings=warnings,
    )


def validate_for_send(draft: Draft) -> list[str]:
    """Onay anında son kontrol (yönetici düzenlemiş olabilir)."""
    problems: list[str] = []
    if not draft.to:
        problems.append("En az bir alıcı gerekli")
    if len(draft.to) > MAX_RECIPIENTS:
        problems.append(f"En fazla {MAX_RECIPIENTS} alıcı")
    problems += [f"Geçersiz e-posta: {a}" for a in draft.to if not is_valid_email(a)]
    if not draft.subject:
        problems.append("Konu boş")
    if draft.action_type == ActionType.SEND_EMAIL and not draft.body:
        problems.append("Mail metni boş")
    return problems
