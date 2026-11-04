import io
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app import db
from app.config import settings
from app.main import app
from app.memory import ProjectFileError, load_project

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "ornek_proje.xlsx"
HEADERS = ["ID", "Görev", "Sorumlu_Mail", "Başlangıç_Tarihi", "Bitiş_Tarihi", "Bağımlı_Olduğu_ID", "Durum"]


def make_xlsx(rows, headers=HEADERS) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def row(id_, deps="", start="2026-11-02", end="2026-11-10", status="Bekliyor", mail="a@x.com"):
    return [id_, f"Görev {id_}", mail, start, end, deps, status]


@pytest.fixture
def memory():
    return load_project(SAMPLE.read_bytes())


# ---- okuma ----------------------------------------------------------------
def test_sample_loads(memory):
    assert len(memory.tasks) == 9
    assert memory.get("5").depends_on == ["2", "4"]
    assert memory.project_end() == date(2027, 1, 29)
    assert memory.participants() >= {"ahmet@example.com", "can@example.com"}


def test_dd_mm_yyyy_dates_and_english_status():
    m = load_project(make_xlsx([row("1", start="02.11.2026", end="13.11.2026", status="done")]))
    assert m.tasks[0].end == date(2026, 11, 13)
    assert m.tasks[0].status == "DONE"


def test_missing_start_column_is_ok():
    headers = [h for h in HEADERS if h != "Başlangıç_Tarihi"]
    m = load_project(make_xlsx([["1", "G", "a@x.com", "2026-11-10", "", "Bekliyor"]], headers))
    assert m.tasks[0].start == m.tasks[0].end


# ---- doğrulama ------------------------------------------------------------
def problems_of(data: bytes) -> list[str]:
    with pytest.raises(ProjectFileError) as e:
        load_project(data)
    return e.value.problems


def test_missing_column():
    p = problems_of(make_xlsx([["1", "G"]], ["ID", "Görev"]))
    assert "sorumlu_mail" in p[0]


def test_row_errors_are_all_reported():
    p = problems_of(make_xlsx([row("1", end="yarın"), row("2", status="belirsiz", mail="bozuk")]))
    text = " ".join(p)
    assert "Satır 2" in text and "Satır 3" in text
    assert "Bitiş_Tarihi" in text and "Durum" in text and "e-posta" in text


def test_unknown_dependency_and_duplicate_id():
    assert any("planda yok" in x for x in problems_of(make_xlsx([row("1", deps="9")])))
    assert any("birden fazla" in x for x in problems_of(make_xlsx([row("1"), row("1")])))


def test_dependency_cycle():
    p = problems_of(make_xlsx([row("1", deps="2"), row("2", deps="1")]))
    assert any("döngü" in x for x in p)


def test_not_an_excel_file():
    assert "okunamadı" in problems_of(b"bu excel degil")[0]


# ---- grafik ve etki -------------------------------------------------------
def test_downstream(memory):
    assert set(memory.downstream("4")) == {"5", "6", "7", "8", "9"}
    assert memory.downstream("9") == []


def test_small_delay_is_absorbed_by_slack(memory):
    r = memory.delay_impact("4", 10)
    assert {i.task_id: i.days_late for i in r.affected} == {"5": 7, "6": 3, "7": 7}
    assert r.project_end_delay_days == 0


def test_large_delay_moves_project_end(memory):
    r = memory.delay_impact("4", 20)
    assert {i.task_id: i.days_late for i in r.affected} == {"5": 17, "6": 13, "7": 17, "8": 10, "9": 7}
    assert r.project_end_delay_days == 7


def test_done_task_is_never_shifted(memory):
    # Görev 3 tamamlandı; 1 numaralı göreve bağlı olsa da kaymaz.
    affected = {i.task_id for i in memory.delay_impact("1", 30).affected}
    assert "3" not in affected and "2" in affected


# ---- API ------------------------------------------------------------------
@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", str(tmp_path / "test.db"))
    return TestClient(app)


def upload(client, data: bytes, name="plan.xlsx"):
    return client.post("/project", files={"file": (name, data)})


def test_api_flow(client):
    assert client.get("/project").status_code == 404
    assert upload(client, SAMPLE.read_bytes()).status_code == 200
    assert len(client.get("/project").json()["tasks"]) == 9
    r = client.get("/project/impact", params={"task_id": "4", "days": 20})
    assert r.json()["project_end_delay_days"] == 7
    assert client.get("/project/impact", params={"task_id": "99", "days": 5}).status_code == 404


def test_api_rejects_bad_files(client):
    assert upload(client, b"x", name="plan.txt").status_code == 400
    r = upload(client, make_xlsx([row("1", deps="9")]))
    assert r.status_code == 422
    assert "planda yok" in r.json()["detail"]["problems"][0]
    assert db.load_latest_project() is None
