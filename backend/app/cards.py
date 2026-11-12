"""Kart yaşam döngüsü: analiz (arka planda) ve onay/ret."""
import logging

from app import db
from app.analysis import AnalysisError, process_email
from app.llm.base import LLMClient, LLMError
from app.memory import ProjectMemory
from app.providers.base import MailProvider, MailProviderError
from app.router import build_draft, validate_for_send
from app.schemas import ActionType, Card, CardStatus, DraftEdit

log = logging.getLogger("chronos.cards")


class CardError(Exception):
    """API'nin kullanıcıya göstereceği iş kuralı hatası."""

    def __init__(self, status_code: int, detail):
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


def analyze_card(card_id: int, memory: ProjectMemory, llm: LLMClient) -> None:
    """Arka plan görevi: mail analiz edilir, taslak çıkarılır, kart güncellenir."""
    card = db.get_card(card_id)
    try:
        result = process_email(card.email, memory, llm)
        draft = build_draft(result.analysis, card.email, memory)
        status = CardStatus.PENDING if draft else CardStatus.NO_ACTION
        db.set_card_analysis(card_id, status, result=result, draft=draft)
    except (LLMError, AnalysisError) as e:
        db.set_card_analysis(card_id, CardStatus.FAILED, error=str(e))
    except Exception:  # kart sonsuza dek PROCESSING'de kalmasın
        log.exception("kart %s analizi beklenmedik şekilde başarısız oldu", card_id)
        db.set_card_analysis(card_id, CardStatus.FAILED, error="Beklenmeyen hata")


def analyze_cards(card_ids: list[int], memory: ProjectMemory, llm: LLMClient) -> None:
    for cid in card_ids:
        analyze_card(cid, memory, llm)


def approve(card_id: int, edit: DraftEdit | None, provider: MailProvider) -> Card:
    card = db.get_card(card_id)
    if card is None:
        raise CardError(404, "Kart bulunamadı")
    if card.status != CardStatus.PENDING or card.draft is None:
        raise CardError(409, f"Kart onaylanamaz, durumu: {card.status.value}")

    draft = card.draft.model_copy(update={k: v for k, v in (edit.model_dump() if edit else {}).items() if v is not None})
    if edit and edit.to is not None:
        draft.to = [a.strip().lower() for a in edit.to]
    problems = validate_for_send(draft)
    if problems:
        raise CardError(422, {"problems": problems})

    # Önce kartı "sahiplen" (atomik); iki kişi aynı anda onaylarsa yalnızca biri gönderir.
    if not db.transition(card_id, CardStatus.PENDING, CardStatus.APPROVED, draft=draft):
        raise CardError(409, "Kart zaten işlendi")
    try:
        if draft.action_type == ActionType.SCHEDULE_MEETING:
            provider.create_meeting(draft.subject, draft.body, draft.to)
        else:
            provider.send_email(draft.to, draft.subject, draft.body)
    except MailProviderError as e:
        db.transition(card_id, CardStatus.APPROVED, CardStatus.PENDING)  # gönderilemedi: tekrar denenebilsin
        raise CardError(502, f"Gönderilemedi: {e}") from e
    return db.get_card(card_id)


def reject(card_id: int) -> Card:
    card = db.get_card(card_id)
    if card is None:
        raise CardError(404, "Kart bulunamadı")
    if not db.transition(card_id, CardStatus.PENDING, CardStatus.REJECTED):
        raise CardError(409, f"Kart reddedilemez, durumu: {card.status.value}")
    return db.get_card(card_id)
