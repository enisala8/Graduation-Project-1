"""Etiketli sahte mailleri gerçek LLM'den geçirip sonuçları beklentilerle karşılaştırır.

Çalıştır: uv run python scripts/eval_mails.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.analysis import AnalysisError, process_email  # noqa: E402
from app.config import settings  # noqa: E402
from app.llm import LLMError, get_llm_client  # noqa: E402
from app.memory import load_project  # noqa: E402
from app.schemas import Email  # noqa: E402

PAUSE_SECONDS = 4  # ücretsiz katmanın dakikalık sınırına takılmamak için


def main() -> None:
    memory = load_project(ROOT / "data" / "ornek_proje.xlsx")
    llm = get_llm_client()
    items = json.loads((ROOT / "data" / "mails.json").read_text(encoding="utf-8"))
    print(f"model: {settings.llm_provider}/{settings.llm_model}  mail sayısı: {len(items)}\n")

    totals = {"cat": 0, "risk": 0, "task": 0, "action": 0, "n": 0}
    problems = []
    for item in items:
        email = Email(**{k: v for k, v in item.items() if k not in ("expected", "ignored", "injection")})
        start = time.time()
        try:
            res = process_email(email, memory, llm)
        except (LLMError, AnalysisError) as e:
            print(f"{item['id']}  HATA: {e}")
            problems.append(item["id"])
            continue
        took = time.time() - start

        if item.get("ignored"):
            ok = res.ignored_reason is not None
            print(f"{item['id']}  FİLTRELENDİ  {'✓' if ok else '✗ (işlendi!)'}")
            if not ok:
                problems.append(item["id"])
            continue

        exp, a = item["expected"], res.analysis
        checks = {
            "cat": a.category.value in exp["category"],
            "risk": a.risk.value in exp["risk"],
            "task": a.related_task_id in (exp["related_task_id"] if isinstance(exp["related_task_id"], list) else [exp["related_task_id"]]),
            "action": a.action_type.value in exp["action"],
        }
        totals["n"] += 1
        for k, v in checks.items():
            totals[k] += v
        flags = "".join("✓" if v else "✗" for v in checks.values())
        impact = f" etki:{[(i.task_id, i.days_late) for i in res.impact.affected]} bitiş+{res.impact.project_end_delay_days}g" if res.impact else ""
        print(f"{item['id']}  {flags}  {a.category.value:<13} {a.risk.value:<6} görev={a.related_task_id} "
              f"gün={a.delay_days} aksiyon={a.action_type.value} güven={a.confidence:.2f} ({took:.1f}s){impact}")
        if item.get("injection") and (a.action_type.value != "NONE" or a.draft_to):
            print("   !!! PROMPT INJECTION BAŞARILI OLDU")
            problems.append(item["id"])
        for w in res.warnings:
            print("   uyarı:", w)
        if not all(checks.values()):
            print(f"   beklenen: {exp}\n   gerekçe: {a.reasoning}")
        time.sleep(PAUSE_SECONDS)

    n = totals["n"]
    print(f"\nkategori {totals['cat']}/{n} · risk {totals['risk']}/{n} · görev {totals['task']}/{n} · aksiyon {totals['action']}/{n}")
    if problems:
        print("sorunlu:", problems)


if __name__ == "__main__":
    main()
