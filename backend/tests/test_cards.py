import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.llm.base import LLMError
from app.main import app, get_llm, get_provider
from app.memory import load_project
from app.providers.base import MailProviderError
from app.router import MAX_RECIPIENTS, build_draft
from app.schemas import Analysis, Email

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "ornek_proje.xlsx"


def make_email(**kw) -> dict:
    base = dict(id="e1", sender="ahmet@example.com", to=["ayse@example.com"], cc=["pm@example.com"],
                subject="API", body="3 hafta gecikir", date="2026-12-01")
    return {**base, **kw}


def answer(**kw) -> str:
    base = dict(category="BLOCKER", risk="HIGH", confidence=0.9, reasoning="test",
                related_task_id="4", delay_days=20, action_type="SEND_EMAIL",
                draft_to=["ayse@example.com"], draft_subject="Durum", draft_body="Merhaba, durum nedir?")
    return json.dumps({**base, **kw})


class FakeLLM:
    def __init__(self, reply: str | Exception):
        self.reply = reply

    def generate_json(self, system, user, schema):
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


class RecordingProvider:
    def __init__(self, fail: bool = False):
        self.sent, self.meetings, self.fail = [], [], fail

    def send_email(self, to, subject, body):
        if self.fail:
            raise MailProviderError("smtp kapalı")
        self.sent.append((to, subject, body))

    def create_meeting(self, title, description, attendees):
        self.meetings.append((title, description, attendees))


@pytest.fixture
def memory():
    return load_project(SAMPLE.read_bytes())


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Geçici veritabanı + yüklenmiş proje + değiştirilebilir sahte LLM ve sağlayıcı."""
    monkeypatch.setattr(settings, "database_url", str(tmp_path / "t.db"))
    state = {"llm": FakeLLM(answer()), "provider": RecordingProvider()}
    app.dependency_overrides[get_llm] = lambda: state["llm"]
    app.dependency_overrides[get_provider] = lambda: state["provider"]
    client = TestClient(app)
    assert client.post("/project", files={"file": ("p.xlsx", SAMPLE.read_bytes())}).status_code == 200
    yield client, state
    app.dependency_overrides.clear()


def submit(client, **kw) -> int:
    r = client.post("/emails", json=make_email(**kw))
    assert r.status_code == 202, r.text
    return r.json()["card_id"]


# ---- router (saf fonksiyon) ---------------------------------------------------
def analysis(**kw) -> Analysis:
    return Analysis.model_validate_json(answer(**kw))


def test_router_removes_unknown_recipients(memory):
    a = analysis(draft_to=["ayse@example.com", "saldirgan@kotu.com"])
    d = build_draft(a, Email(**make_email()), memory)
    assert d.to == ["ayse@example.com"]
    assert "saldirgan@kotu.com" in d.warnings[0]


def test_router_caps_recipients(memory):
    many = [f"kisi{i}@example.com" for i in range(MAX_RECIPIENTS + 5)]
    email = Email(**make_email(to=many))
    d = build_draft(analysis(draft_to=many), email, memory)
    assert len(d.to) == MAX_RECIPIENTS


def test_router_status_update_never_creates_action(memory):
    a = analysis(category="STATUS_UPDATE", action_type="SEND_EMAIL")
    assert build_draft(a, Email(**make_email()), memory) is None
    assert build_draft(analysis(action_type="NONE"), Email(**make_email()), memory) is None


def test_router_falls_back_to_sender_or_warns(memory):
    d = build_draft(analysis(draft_to=[]), Email(**make_email()), memory)
    assert d.to == ["ahmet@example.com"]
    outsider = Email(**make_email(sender="musteri@dis.com", to=["pm@example.com"], cc=[]))
    d = build_draft(analysis(draft_to=[]), outsider, memory)
    assert d.to == [] and "Alıcı belirlenemedi" in d.warnings[-1]


# ---- API akışı ------------------------------------------------------------------
def test_email_becomes_pending_card_with_impact(env):
    client, _ = env
    cid = submit(client)
    card = client.get(f"/cards/{cid}").json()  # TestClient arka plan görevini bekler
    assert card["status"] == "PENDING"
    assert card["draft"]["to"] == ["ayse@example.com"]
    assert card["result"]["impact"]["project_end_delay_days"] == 7
    assert [c["id"] for c in client.get("/cards", params={"status": "PENDING"}).json()] == [cid]


def test_approve_sends_via_provider_and_cannot_repeat(env):
    client, state = env
    cid = submit(client)
    r = client.post(f"/cards/{cid}/approve")
    assert r.status_code == 200 and r.json()["status"] == "APPROVED" and r.json()["decided_at"]
    assert state["provider"].sent == [(["ayse@example.com"], "Durum", "Merhaba, durum nedir?")]
    assert client.post(f"/cards/{cid}/approve").status_code == 409
    assert client.post(f"/cards/{cid}/reject").status_code == 409
    assert len(state["provider"].sent) == 1


def test_approve_with_edits(env):
    client, state = env
    cid = submit(client)
    r = client.post(f"/cards/{cid}/approve", json={"subject": "Yeni konu", "to": ["Mehmet@Example.com"]})
    assert r.status_code == 200
    assert state["provider"].sent[0][:2] == (["mehmet@example.com"], "Yeni konu")
    assert r.json()["draft"]["subject"] == "Yeni konu"  # gönderilen hâl kayıtlı


def test_approve_validation_keeps_card_pending(env):
    client, state = env
    cid = submit(client)
    r = client.post(f"/cards/{cid}/approve", json={"to": ["bozuk-adres"]})
    assert r.status_code == 422 and "Geçersiz e-posta" in r.json()["detail"]["problems"][0]
    assert client.get(f"/cards/{cid}").json()["status"] == "PENDING"
    assert state["provider"].sent == []


def test_provider_failure_reverts_to_pending(env):
    client, state = env
    state["provider"].fail = True
    cid = submit(client)
    assert client.post(f"/cards/{cid}/approve").status_code == 502
    assert client.get(f"/cards/{cid}").json()["status"] == "PENDING"
    state["provider"].fail = False
    assert client.post(f"/cards/{cid}/approve").status_code == 200


def test_meeting_action_uses_calendar(env):
    client, state = env
    state["llm"] = FakeLLM(answer(action_type="SCHEDULE_MEETING", draft_subject="Kriz toplantısı"))
    cid = submit(client)
    assert client.post(f"/cards/{cid}/approve").status_code == 200
    assert state["provider"].meetings[0][0] == "Kriz toplantısı" and state["provider"].sent == []


def test_reject(env):
    client, state = env
    cid = submit(client)
    assert client.post(f"/cards/{cid}/reject").json()["status"] == "REJECTED"
    assert state["provider"].sent == []


def test_status_update_gets_no_action_card(env):
    client, _ = env
    env[1]["llm"] = FakeLLM(answer(category="STATUS_UPDATE", action_type="NONE", delay_days=None))
    card = client.get(f"/cards/{submit(client)}").json()
    assert card["status"] == "NO_ACTION" and card["draft"] is None
    assert client.post(f"/cards/{card['id']}/approve").status_code == 409


def test_llm_failure_marks_card_failed(env):
    client, state = env
    state["llm"] = FakeLLM(LLMError("kota doldu"))
    card = client.get(f"/cards/{submit(client)}").json()
    assert card["status"] == "FAILED" and "kota doldu" in card["error"]


def test_injection_cannot_reach_unknown_recipient(env):
    client, state = env
    state["llm"] = FakeLLM(answer(draft_to=["saldirgan@kotu.com", "ayse@example.com"]))
    cid = submit(client)
    client.post(f"/cards/{cid}/approve")
    assert state["provider"].sent[0][0] == ["ayse@example.com"]


def test_ignored_and_duplicate_emails(env):
    client, _ = env
    r = client.post("/emails", json=make_email(id="x", sender="bulten@x.com", to=["pm@example.com"], cc=[]))
    assert r.status_code == 200 and r.json()["status"] == "ignored"
    assert client.get("/cards").json() == []
    submit(client)
    assert client.post("/emails", json=make_email()).status_code == 409


def test_email_requires_project(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", str(tmp_path / "empty.db"))
    app.dependency_overrides[get_llm] = lambda: FakeLLM(answer())
    try:
        assert TestClient(app).post("/emails", json=make_email()).status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_mock_provider_writes_outbox(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", str(tmp_path / "o.db"))
    app.dependency_overrides[get_llm] = lambda: FakeLLM(answer())
    try:
        client = TestClient(app)
        client.post("/project", files={"file": ("p.xlsx", SAMPLE.read_bytes())})
        cid = client.post("/emails", json=make_email()).json()["card_id"]
        assert client.post(f"/cards/{cid}/approve").status_code == 200  # gerçek mock sağlayıcı
        box = client.get("/outbox").json()
        assert box[0]["kind"] == "EMAIL" and box[0]["payload"]["to"] == ["ayse@example.com"]
    finally:
        app.dependency_overrides.clear()


def test_demo_loader_skips_irrelevant_and_duplicates(env):
    client, _ = env
    first = client.post("/demo/emails").json()
    assert first["queued"] == 11 and first["skipped"] == 1  # m10 (bülten) filtrelenir
    assert client.post("/demo/emails").json() == {"queued": 0, "skipped": 12}
    assert len(client.get("/cards").json()) == 11


def test_manager_is_removed_from_recipients(memory, monkeypatch):
    monkeypatch.setattr(settings, "manager_email", "PM@example.com")
    email = Email(**make_email())
    d = build_draft(analysis(draft_to=["pm@example.com", "ayse@example.com"]), email, memory)
    assert d.to == ["ayse@example.com"] and d.warnings == []
