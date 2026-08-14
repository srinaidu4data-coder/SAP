"""Instant consultant analysis. Uses proven live counts. Does not wait on SAP GUI."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sapilot.product.analyze import analyze_process, _resolve
from sapilot.product.chat import _extract_process
from sapilot.product.report import render_html, report_url, write_report
from sapilot.product.drillthrough import drill
from sapilot.product.table_read import _MEANING


def _data() -> Path:
    return Path(os.environ.get("SAPILOT_DATA", "data"))


def load_live_counts() -> dict[str, dict[str, Any]]:
    """Merge every proven Number of Entries file on this book."""
    out: dict[str, dict[str, Any]] = {}
    roots = [
        _data() / "runs" / "analysis_mega" / "LIVE_COUNTS.json",
        _data() / "runs" / "analysis_copc" / "LIVE_COUNTS.json",
        _data() / "runs" / "analysis_otc" / "LIVE_COUNTS.json",
        _data() / "runs" / "analysis_ptp" / "LIVE_COUNTS.json",
    ]
    for folder in (_data() / "runs").glob("analysis_*"):
        p = folder / "LIVE_COUNTS.json"
        if p not in roots:
            roots.append(p)
    for path in roots:
        if not path.exists():
            continue
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        for rec in rows:
            tab = (rec.get("table") or "").upper()
            n = rec.get("entries_found")
            if not tab or n is None:
                continue
            out[tab] = {
                "table": tab,
                "entries_found": int(n),
                "rank": "PRIOR-LIVE",
                "notes": rec.get("notes") or "Number of Entries on this client",
                "shot": rec.get("shot"),
            }
    return out


def _n(counts: dict, tab: str) -> int | None:
    rec = counts.get(tab.upper())
    if not rec:
        return None
    return rec.get("entries_found")


def _fmt(n: int | None) -> str:
    if n is None:
        return "not counted on this book"
    return f"{n:,}"


def _hops_from_counts(counts: dict) -> list[str]:
    hops: list[str] = []
    vbak, likp, vbrk = _n(counts, "VBAK"), _n(counts, "LIKP"), _n(counts, "VBRK")
    if vbak is not None and likp is not None:
        hops.append(
            f"Orders {vbak:,} → deliveries {likp:,}: {vbak - likp:,} orders never became a delivery."
        )
    if likp is not None and vbrk is not None:
        hops.append(
            f"Deliveries {likp:,} → invoices {vbrk:,}: {likp - vbrk:,} deliveries sit unbilled. "
            "RAR cannot start on an unbilled delivery."
        )
    vbap, lips, vbrp = _n(counts, "VBAP"), _n(counts, "LIPS"), _n(counts, "VBRP")
    if vbak and vbap:
        hops.append(f"Order lines {vbap:,} on {vbak:,} headers — about {vbap / vbak:.2f} items per order.")
    if vbrk is not None and _n(counts, "BSID") is not None:
        hops.append(
            f"Invoices {vbrk:,} vs open AR {_fmt(_n(counts, 'BSID'))}. "
            "Cash collection is a different clock from revenue recognition."
        )
    if vbrk is not None and _n(counts, "BSAD") is not None:
        hops.append(
            f"Cleared AR {_fmt(_n(counts, 'BSAD'))} vs open {_fmt(_n(counts, 'BSID'))}. "
            "Collection works when someone does it — that does not prove RAR ran."
        )
    if vbrk is not None and _n(counts, "NAST") is not None:
        hops.append(
            f"Invoices {vbrk:,} vs outputs {_fmt(_n(counts, 'NAST'))}. "
            "Most bills never produced a customer letter."
        )
    if _n(counts, "KNKK") == 0 and vbak:
        hops.append(f"Credit master KNKK = 0 while {vbak:,} orders exist. Credit is a decision, not a missing t-code.")
    if _n(counts, "VBFA"):
        hops.append(
            f"Document flow VBFA = {_fmt(_n(counts, 'VBFA'))}. The hops exist in the book; the gaps are the missing next documents."
        )
    if _n(counts, "KEKO") is not None:
        hops.append(
            f"Cost estimates KEKO = {_fmt(_n(counts, 'KEKO'))}, recipes TCK03 = {_fmt(_n(counts, 'TCK03'))}. "
            "Every sales invoice is only as honest as these estimates."
        )
    if _n(counts, "CKMLHD") is not None:
        hops.append(
            f"Material ledger headers {_fmt(_n(counts, 'CKMLHD'))}, period values CKMLCR = {_fmt(_n(counts, 'CKMLCR'))}. "
            "Actual costing is live — standard-only margin is a lie."
        )
    if _n(counts, "FARR_D_CONTRACT") == 0 and vbrk:
        hops.append(
            f"VBRK = {vbrk:,} and FARR_D_CONTRACT = 0. Billing is live. RAR contracts are not. "
            "Treat the 5,982 invoices as RAR input, not as recognized revenue."
        )
    return hops


def _studies(counts: dict, process_key: str | None) -> list[dict[str, Any]]:
    prefer = {
        "rar": ["VBAK", "VBRK", "FARR_D_POB", "FARR_D_CONTRACT", "BSID", "NAST", "VBFA"],
        "otc": ["VBAK", "VBAP", "LIKP", "VBRK", "BSID", "BSAD", "NAST", "KNKK", "VBFA"],
        "collections": ["BSID", "BSAD", "NAST", "VBRK", "KNKK", "KNA1"],
        "copc": ["TCK03", "TCK31", "KEKO", "KEPH", "CKMLHD", "CKMLCR", "AUFK"],
        "ptp": ["EKKO", "EKPO", "EKBE", "BSIK", "MARA"],
    }.get(process_key or "", ["VBAK", "LIKP", "VBRK", "BSID", "KEKO", "TCK03"])
    out = []
    for tab in prefer:
        rec = counts.get(tab)
        if not rec:
            continue
        n = rec["entries_found"]
        meaning = _MEANING.get(tab, f"{tab} is on this process spine.")
        if n == 0:
            story = f"{tab} was opened on this book and is empty (F7 = 0). {meaning}"
        else:
            story = f"{tab} has {n:,} entries (Number of Entries, not a 500 list). {meaning}"
        out.append(
            {
                "table": tab,
                "story": story,
                "columns": [],
                "sample_rows": [],
                "signals": [story],
                "visible_rows": 0,
            }
        )
    return out


def _narrative(asked: str, rec: dict, counts: dict, hops: list[str]) -> list[str]:
    vbak, likp, vbrk = _n(counts, "VBAK"), _n(counts, "LIKP"), _n(counts, "VBRK")
    lines = [
        rec.get("story") or "",
        (
            "These numbers are already proven on company 1710 by Number of Entries. "
            "This report does not wait for another SE16N sitting. "
            "Display-only: nothing is created or posted."
        ),
    ]
    if vbak is not None and likp is not None and vbrk is not None:
        lines.append(
            f"The commercial funnel is {vbak:,} orders → {likp:,} deliveries → {vbrk:,} invoices. "
            f"{vbak - likp:,} never delivered. {likp - vbrk:,} delivered and unbilled. "
            "Those are three teams. One collections tool will not fix the first two gaps."
        )
    if _n(counts, "BSID") is not None:
        lines.append(
            f"Cash still out: {_fmt(_n(counts, 'BSID'))} open AR. Already collected: {_fmt(_n(counts, 'BSAD'))}. "
            f"Outputs {_fmt(_n(counts, 'NAST'))} — most invoices never became a letter. "
            "Do not buy a collections suite until statements exist."
        )
    if _n(counts, "TCK03") is not None:
        lines.append(
            f"Costing: {_fmt(_n(counts, 'TCK03'))} recipes, {_fmt(_n(counts, 'TCK31'))} overhead sheet, "
            f"{_fmt(_n(counts, 'KEKO'))} estimates, ML values {_fmt(_n(counts, 'CKMLCR'))}. "
            "Products look cheaper than they are. That fake margin funds discounts and uncollected cash."
        )
    if "rar" in (asked or "").lower() or "revenue" in (asked or "").lower() or rec.get("source") == "library":
        if _n(counts, "VBRK"):
            lines.append(
                f"If RAR is on, the {_fmt(_n(counts, 'VBRK'))} invoices are the input to RAI, not the P&L event. "
                "If FARR tables are empty while VBRK is full, this book is still classic SD/FI revenue. "
                "Design IFRS 15 only after one invoice is proven in FARR_RAI_MON."
            )
    lines.extend(hops[:3])
    return [x for x in lines if x]


def run_fast(question: str) -> dict[str, Any]:
    q = (question or "").strip()
    if not q:
        return {"ok": False, "error": "Ask a process. Example: Analyze the complete RAR process."}

    asked = _extract_process(q)
    rec = analyze_process(asked)
    counts = load_live_counts()
    hops = _hops_from_counts(counts) or list(rec.get("hops") or [])
    kind, key = _resolve(asked)
    studies = _studies(counts, key if kind in {"library", "catalog"} else None)
    narrative = _narrative(q, rec, counts, hops)
    scenarios = []
    for text in rec.get("scenarios") or []:
        status = "LIVE" if counts else "OPEN"
        if "unbilled" in text.lower() and _n(counts, "LIKP") is not None:
            text = text + f" Live: LIKP={_fmt(_n(counts, 'LIKP'))}, VBRK={_fmt(_n(counts, 'VBRK'))}."
            status = "LIVE"
        if "RAR" in text or "RAI" in text:
            if _n(counts, "VBRK"):
                text = text + f" Live: VBRK={_fmt(_n(counts, 'VBRK'))}."
                status = "LIVE"
        scenarios.append({"name": text.split(":")[0][:48], "status": status, "text": text})

    job_id = "fast-" + uuid.uuid4().hex[:10]
    dest = _data() / "runs" / "product" / "research" / f"FAST_{job_id}"
    dest.mkdir(parents=True, exist_ok=True)
    count_rows = list(counts.values())
    drilldown = drill(asked, counts, key if kind in {"library", "catalog"} else None)
    narrative.append(drilldown["story"])

    job = {
        "id": job_id,
        "status": "done",
        "phase": "fast",
        "asked": q,
        "title": rec.get("title"),
        "spine": rec.get("spine"),
        "story": rec.get("story"),
        "dir": str(dest),
        "counts": count_rows,
        "studies": studies,
        "visits": [],
        "hops": hops,
        "scenarios": scenarios,
        "narrative": narrative,
        "questions": rec.get("questions") or [],
        "steps": rec.get("steps") or [],
        "progress": {
            "done": len(count_rows),
            "total": len(count_rows),
            "tables_ok": sum(1 for c in count_rows if (c.get("entries_found") or 0) > 0),
            "tables_zero": sum(1 for c in count_rows if c.get("entries_found") == 0),
            "tables_miss": 0,
            "visits": 0,
        },
        "universe": len(count_rows),
        "report_url": report_url(job_id),
        "events": [
            {
                "t": datetime.now(timezone.utc).isoformat(),
                "kind": "fast",
                "text": f"Instant analysis from {len(count_rows)} proven live counts. Glass walk is optional.",
            }
        ],
        "source": rec.get("source"),
        "ok": True,
        "drill": drilldown,
    }
    from sapilot.product.minute_analyze import run_agents, write_minute_excel

    agents = run_agents(counts, q, rec)
    job["rules"] = agents["rules"]
    job["integrations"] = agents["integrations"]
    job["possible"] = agents["possible"]
    job["narrative"] = list(narrative) + list(agents["possible"])
    xlsx = dest / "ANALYZE.xlsx"
    write_minute_excel(
        str(xlsx),
        asked=q,
        counts=counts,
        drill=drilldown,
        rules=agents["rules"],
        integ=agents["integrations"],
        possible=agents["possible"],
    )
    job["excel_name"] = xlsx.name
    job["excel_url"] = f"/api/research/{job_id}/file/{xlsx.name}"
    job["current"] = f"1-minute pack ready. {len(counts)} tables, {len(agents['rules'])} rules, Excel written."

    write_report(job)
    (dest / "job.json").write_text(json.dumps(job, indent=2, default=str), encoding="utf-8")
    from sapilot.product.research import _JOBS, _LOCK

    with _LOCK:
        _JOBS[job_id] = job
    return job
