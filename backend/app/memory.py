"""Proje hafızası: Excel -> doğrulanmış görev listesi + bağımlılık grafiği.

Ajanın "projeyi tanıması" bu modülle olur. Gecikme etkisi LLM'e bırakılmaz,
burada deterministik olarak hesaplanır; LLM'e yalnızca sonuç verilir.
"""
import io
import re
from datetime import date, timedelta
from enum import Enum
from pathlib import Path

import pandas as pd
from pydantic import BaseModel


class Status(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    BLOCKED = "BLOCKED"


class Task(BaseModel):
    id: str
    name: str
    owner_email: str
    start: date
    end: date
    depends_on: list[str] = []
    status: Status


class Impact(BaseModel):
    task_id: str
    name: str
    owner_email: str
    days_late: int
    new_end: date


class ImpactReport(BaseModel):
    task_id: str
    delay_days: int
    affected: list[Impact]
    project_end_delay_days: int


class ProjectFileError(Exception):
    """Excel dosyası geçersiz. `problems` kullanıcıya gösterilecek hata listesi."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


class ProjectMemory(BaseModel):
    tasks: list[Task]

    # ---- sorgular --------------------------------------------------------
    def get(self, task_id: str) -> Task | None:
        return next((t for t in self.tasks if t.id == task_id), None)

    def participants(self) -> set[str]:
        """Planda adı geçen tüm e-posta adresleri (Gmail filtresi için)."""
        return {t.owner_email for t in self.tasks}

    def tasks_for(self, email: str) -> list[Task]:
        return [t for t in self.tasks if t.owner_email == email.lower()]

    def project_end(self) -> date:
        return max(t.end for t in self.tasks)

    def to_context(self) -> dict:
        """LLM prompt'una konacak sade sözlük."""
        return {
            "project_end": self.project_end().isoformat(),
            "tasks": [t.model_dump(mode="json") for t in self.tasks],
        }

    # ---- grafik ----------------------------------------------------------
    def _topo_order(self) -> list[str] | None:
        """Kahn algoritması. Döngü varsa None döner."""
        indeg = {t.id: len(t.depends_on) for t in self.tasks}
        children: dict[str, list[str]] = {t.id: [] for t in self.tasks}
        for t in self.tasks:
            for p in t.depends_on:
                children[p].append(t.id)
        queue = [i for i, d in indeg.items() if d == 0]
        order: list[str] = []
        while queue:
            n = queue.pop(0)
            order.append(n)
            for c in children[n]:
                indeg[c] -= 1
                if indeg[c] == 0:
                    queue.append(c)
        return order if len(order) == len(self.tasks) else None

    def validate_graph(self) -> list[str]:
        problems: list[str] = []
        ids = [t.id for t in self.tasks]
        for dup in sorted({i for i in ids if ids.count(i) > 1}):
            problems.append(f"ID birden fazla satırda kullanılmış: {dup}")
        known = set(ids)
        for t in self.tasks:
            if t.start > t.end:
                problems.append(f"Görev {t.id}: başlangıç tarihi bitişten sonra")
            for p in t.depends_on:
                if p == t.id:
                    problems.append(f"Görev {t.id}: kendine bağımlı olamaz")
                elif p not in known:
                    problems.append(f"Görev {t.id}: bağımlı olduğu ID '{p}' planda yok")
        if not problems and self._topo_order() is None:
            problems.append("Bağımlılıklarda döngü var (görevler birbirini bekliyor)")
        return problems

    def downstream(self, task_id: str) -> list[str]:
        """Bu görev gecikirse (dolaylı olarak da) etkilenebilecek tüm görev ID'leri."""
        children: dict[str, list[str]] = {t.id: [] for t in self.tasks}
        for t in self.tasks:
            for p in t.depends_on:
                children[p].append(t.id)
        seen: list[str] = []
        stack = list(children.get(task_id, []))
        while stack:
            n = stack.pop()
            if n not in seen:
                seen.append(n)
                stack.extend(children[n])
        return seen

    def delay_impact(self, task_id: str, days: int) -> ImpactReport:
        """`task_id` görevi `days` gün gecikirse zincirleme etkiyi hesaplar.

        Model: bitiş-başlangıç (finish-to-start). Bir görev, bağımlı olduğu
        görevlerin bitişinden önce başlayamaz. Plandaki boşluk (slack) gecikmeyi
        emer; sığmayan kısım görevi kaydırır ve sürede değişiklik olmaz.
        """
        if self.get(task_id) is None:
            raise KeyError(task_id)
        order = self._topo_order()
        if order is None:
            raise ValueError("bağımlılık grafiğinde döngü var")

        shift: dict[str, int] = {}
        for tid in order:
            t = self.get(tid)
            if tid == task_id:
                shift[tid] = days
                continue
            if t.status == Status.DONE or not t.depends_on:
                shift[tid] = 0
                continue
            old_ready = max(self.get(p).end for p in t.depends_on)
            new_ready = max(self.get(p).end + timedelta(days=shift[p]) for p in t.depends_on)
            old_start = max(t.start, old_ready)
            new_start = max(t.start, new_ready)
            shift[tid] = (new_start - old_start).days

        affected = [
            Impact(
                task_id=t.id, name=t.name, owner_email=t.owner_email,
                days_late=shift[t.id], new_end=t.end + timedelta(days=shift[t.id]),
            )
            for t in self.tasks
            if t.id != task_id and shift[t.id] > 0
        ]
        new_project_end = max(t.end + timedelta(days=shift[t.id]) for t in self.tasks)
        return ImpactReport(
            task_id=task_id,
            delay_days=days,
            affected=affected,
            project_end_delay_days=max(0, (new_project_end - self.project_end()).days),
        )


# ---- Excel okuma ---------------------------------------------------------
_TR = str.maketrans("ıİşŞçÇğĞöÖüÜ", "iIsScCgGoOuU")
REQUIRED = ["id", "gorev", "sorumlu_mail", "bitis_tarihi", "durum"]
OPTIONAL = ["baslangic_tarihi", "bagimli_oldugu_id"]

_STATUS_WORDS = {
    Status.DONE: {"tamamlandi", "bitti", "done", "completed"},
    Status.IN_PROGRESS: {"devam ediyor", "devam", "in progress", "in_progress"},
    Status.TODO: {"bekliyor", "baslamadi", "todo", "not started", "planned"},
    Status.BLOCKED: {"engelli", "bloke", "blocked"},
}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", "_", str(h).translate(_TR).strip().lower())


def _norm_id(v: str) -> str:
    v = str(v).strip()
    return v[:-2] if v.endswith(".0") else v  # Excel 1 sayısını "1.0" yapabilir


def _parse_date(v: str) -> date | None:
    """ISO (2026-12-11, Excel'in tarih hücreleri) ve gg.aa.yyyy / gg/aa/yyyy okur.

    ISO'yu dayfirst ile okumak gün ile ayı yer değiştirir (11 Aralık -> 12 Kasım),
    bu yüzden biçimler tek tek, açıkça ayrılır.
    """
    s = v.strip()
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}", s):
            return date.fromisoformat(s[:10])
        m = re.match(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$", s)
        if m:
            d, mo, y = map(int, m.groups())
            return date(y, mo, d)
    except ValueError:
        return None
    return None


def _parse_status(v: str) -> Status | None:
    key = v.translate(_TR).strip().lower()
    return next((s for s, words in _STATUS_WORDS.items() if key in words), None)


def load_project(source: str | Path | bytes) -> ProjectMemory:
    """Excel'i okur ve doğrular; hata varsa tüm sorunları tek seferde bildirir."""
    try:
        buf = io.BytesIO(source) if isinstance(source, bytes) else source
        df = pd.read_excel(buf, dtype=str)
    except Exception as e:  # bozuk/yanlış formatlı dosya
        raise ProjectFileError([f"Excel dosyası okunamadı: {e}"]) from e

    df.columns = [_norm_header(c) for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ProjectFileError([
            "Eksik sütun(lar): " + ", ".join(missing),
            "Beklenen sütunlar: ID, Görev, Sorumlu_Mail, Başlangıç_Tarihi (isteğe bağlı), "
            "Bitiş_Tarihi, Bağımlı_Olduğu_ID (isteğe bağlı), Durum",
        ])
    for c in OPTIONAL:
        if c not in df.columns:
            df[c] = ""
    df = df.fillna("")
    df = df[(df != "").any(axis=1)]  # tamamen boş satırları at

    problems: list[str] = []
    tasks: list[Task] = []
    for idx, row in df.iterrows():
        line = idx + 2  # Excel'de başlık 1. satır
        tid = _norm_id(row["id"])
        email = row["sorumlu_mail"].strip().lower()
        end = _parse_date(row["bitis_tarihi"])
        start = _parse_date(row["baslangic_tarihi"]) if row["baslangic_tarihi"].strip() else end
        status = _parse_status(row["durum"])
        if not tid:
            problems.append(f"Satır {line}: ID boş")
        if not row["gorev"].strip():
            problems.append(f"Satır {line}: Görev adı boş")
        if not _EMAIL.match(email):
            problems.append(f"Satır {line}: geçersiz e-posta '{row['sorumlu_mail']}'")
        if end is None:
            problems.append(f"Satır {line}: Bitiş_Tarihi okunamadı '{row['bitis_tarihi']}'")
        if start is None:
            problems.append(f"Satır {line}: Başlangıç_Tarihi okunamadı '{row['baslangic_tarihi']}'")
        if status is None:
            problems.append(f"Satır {line}: bilinmeyen Durum '{row['durum']}'")
        if tid and end and start and status and _EMAIL.match(email) and row["gorev"].strip():
            deps = [_norm_id(d) for d in re.split(r"[,;]", row["bagimli_oldugu_id"]) if d.strip()]
            tasks.append(Task(id=tid, name=row["gorev"].strip(), owner_email=email,
                              start=start, end=end, depends_on=deps, status=status))
    if problems:
        raise ProjectFileError(problems)
    if not tasks:
        raise ProjectFileError(["Excel'de hiç görev satırı yok"])

    memory = ProjectMemory(tasks=tasks)
    problems = memory.validate_graph()
    if problems:
        raise ProjectFileError(problems)
    return memory
