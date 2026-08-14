"""Answer a natural-language analysis question. Works without an LLM key."""
from __future__ import annotations

import re

from sapilot.product.analyze import analyze_process, _resolve

_FACT = (
    "On company 1710 we already counted: 12,255 sales orders, 7,959 deliveries, "
    "5,982 customer invoices, 3,014 unpaid, 5,174 collected, 928 outputs, "
    "zero credit masters, 3,472 cost estimates, 74 costing recipes, one overhead sheet, "
    "a live shop floor (~2,500 production orders, 1,838 confirmations), "
    "and years of actual costing. Goods receipts already posted on MZ-RM materials; "
    "TG10 is drop-ship, not warehouse stock."
)


def _extract_process(text: str) -> str:
    t = (text or "").strip()
    # "analyze RAR", "analyse the complete RAR process", "RAR process"
    m = re.search(
        r"(?:analy[sz]e|walk|review|explain|map)\s+(?:the\s+)?(?:complete\s+)?(?:full\s+)?"
        r"(.+?)(?:\s+process)?(?:\s+with\b.*)?$",
        t,
        re.I,
    )
    if m:
        return m.group(1).strip(" .")
    # bare name
    if len(t.split()) <= 6:
        return t
    return t


def _format(rec: dict) -> str:
    lines = [
        f"**{rec.get('title') or rec.get('asked')}**",
        "",
        rec.get("story") or "",
        "",
        f"**Spine:** {rec.get('spine') or ''}",
        "",
        "**How it connects**",
    ]
    for h in rec.get("hops") or []:
        lines.append(f"- {h}")
    if rec.get("scenarios"):
        lines += ["", "**Granular scenarios**"]
        for s in rec["scenarios"]:
            lines.append(f"- {s}")
    lines += ["", "**Ask on the glass**"]
    for q in rec.get("questions") or []:
        lines.append(f"- {q}")
    lines += ["", "**Open these in display only** (click a button under this answer)"]
    for s in rec.get("steps") or []:
        flag = "" if s.get("allowed") else " — not on the display list yet; use SE16N"
        lines.append(f"- {s.get('tcode')} ({s.get('phase')}): {s.get('purpose')}{flag}")
    lines += ["", _FACT]
    return "\n".join(lines).strip()


def _try_llm(question: str, grounded: str) -> str | None:
    try:
        from sapilot.brain.router import ModelRouter, Role

        r = ModelRouter()
        if not (r.xai_key or r.openai_key):
            return None
        return r.complete(
            Role.PLANNING,
            "You are SAPILOT, a process consultant at the SAP glass. "
            "Answer in business language. Do not invent counts. "
            "Use only the grounded facts. Display-only: never tell them to post or create. "
            "Connect hops. Give alternatives and next steps. No table-field dumps.",
            f"Question:\n{question}\n\nGrounded analysis:\n{grounded}",
            temperature=0.3,
            json_mode=False,
        )
    except Exception:
        return None


def answer(question: str) -> dict:
    q = (question or "").strip()
    if not q:
        return {"ok": False, "error": "Ask a question. Example: Analyze the complete RAR process."}

    process = _extract_process(q)
    kind, key = _resolve(process)
    rec = analyze_process(process if (kind != "generic" or len(process.split()) <= 8) else q)
    grounded = _format(rec)
    text = _try_llm(q, grounded) or grounded
    steps = [s for s in (rec.get("steps") or []) if s.get("allowed")]
    return {
        "ok": True,
        "text": text,
        "asked": q,
        "process": rec.get("asked") or process,
        "title": rec.get("title"),
        "steps": steps,
        "source": rec.get("source"),
    }
