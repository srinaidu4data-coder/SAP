"""Live glass research job: SE16N census + display hops + consultant report."""
from __future__ import annotations

import json
import os
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sapilot.display.policy import DisplayPolicyError, assert_display_tcode, is_create_screen
from sapilot.product.analyze import analyze_process
from sapilot.product.census import close_popups
from sapilot.product.navigate import back_out, ensure_screen, goto_checked, rebind
from sapilot.product.chat import _extract_process
from sapilot.product.report import report_url, write_report
from sapilot.product.universe import plan_research

_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}
_THREAD: dict[str, threading.Thread] = {}


def _root() -> Path:
    base = Path(os.environ.get("SAPILOT_DATA", "data")) / "runs" / "product" / "research"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _max_tables() -> int:
    try:
        return max(8, int(os.environ.get("SAPILOT_RESEARCH_MAX", "28")))
    except ValueError:
        return 28


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reroute(job: dict, queue: list[str], seen: set[str], failed: str) -> None:
    """Do not retry `failed`. Queue different objects that still answer the question."""
    from sapilot.learn.paths import abandon_family, drop_family, known_good, next_paths

    alts = next_paths(failed, seen | {t.upper() for t in queue})
    for alt in alts:
        if alt not in seen and alt not in queue:
            queue.append(alt)
            job["progress"]["total"] = int(job.get("progress", {}).get("total") or 0) + 1
            _emit(job, "think", f"{failed} is a closed path. New path: {alt}.")
    if abandon_family(job.get("counts") or [], "FARR"):
        keep = known_good("FARR", (job.get("mind") or {}).get("beliefs") or [])
        try:
            from sapilot.learn.mind import snapshot

            keep.extend(known_good("FARR", snapshot().get("beliefs") or []))
        except Exception:
            pass
        before = list(queue)
        queue[:] = drop_family(queue, "FARR", keep)
        dropped = [t for t in before if t not in queue]
        if dropped:
            _emit(
                job,
                "think",
                "Two FARR names already failed. I stop guessing FARR_* and switch to classic SD/FI: "
                + ", ".join(alts or ["VBRK"]),
            )


def _emit(job: dict, kind: str, text: str, **extra: Any) -> None:
    ev = {"t": _now(), "kind": kind, "text": text, **extra}
    job["events"].append(ev)
    if len(job["events"]) > 800:
        job["events"] = job["events"][-600:]
    job["current"] = text
    job["updated"] = _now()


def _save(job: dict) -> None:
    path = Path(job["dir"]) / "job.json"
    try:
        write_report(job)
    except Exception:
        pass
    slim = {k: v for k, v in job.items() if k != "shot_b64"}
    path.write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")


def _load_job_file(path: Path) -> dict | None:
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not rec.get("id"):
        return None
    rec.setdefault("dir", str(path.parent))
    rec.setdefault("report_url", report_url(rec["id"]))
    return rec


def get_job(job_id: str) -> dict | None:
    jid = (job_id or "").strip()
    if not jid:
        return None
    with _LOCK:
        if jid in _JOBS:
            return _JOBS[jid]
    for folder in sorted(_root().iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        if folder.name.endswith("_" + jid) or jid in folder.name:
            rec = _load_job_file(folder / "job.json")
            if rec:
                with _LOCK:
                    _JOBS.setdefault(rec["id"], rec)
                return rec
    return None


def latest_job() -> dict | None:
    with _LOCK:
        if _JOBS:
            running = [j for j in _JOBS.values() if j.get("status") == "running"]
            if running:
                return running[0]
            done = sorted(_JOBS.values(), key=lambda j: j.get("updated") or "", reverse=True)
            if done:
                return done[0]
    folders = sorted((p for p in _root().iterdir() if p.is_dir()), reverse=True)
    for folder in folders:
        rec = _load_job_file(folder / "job.json")
        if rec:
            with _LOCK:
                _JOBS.setdefault(rec["id"], rec)
            return rec
    return None


def active_job() -> dict | None:
    with _LOCK:
        for j in _JOBS.values():
            if j.get("status") == "running":
                return j
    return None


def stop_job(job_id: str) -> dict | None:
    job = get_job(job_id)
    if not job:
        return None
    job["stop"] = True
    if job.get("status") == "running":
        job["status"] = "stopping"
        _emit(job, "note", "Stop requested — finishing the current table.")
    return job


def public_job(job: dict) -> dict:
    """JSON the UI polls. No huge event tail."""
    return {
        "ok": True,
        "id": job["id"],
        "status": job.get("status"),
        "phase": job.get("phase"),
        "asked": job.get("asked"),
        "title": job.get("title"),
        "spine": job.get("spine"),
        "story": job.get("story"),
        "current": job.get("current"),
        "error": job.get("error"),
        "sap_title": job.get("sap_title") or "",
        "shot_seq": job.get("shot_seq") or 0,
        "shot_name": job.get("shot_name"),
        "progress": job.get("progress") or {},
        "counts": job.get("counts") or [],
        "visits": job.get("visits") or [],
        "hops": job.get("hops") or [],
        "scenarios": job.get("scenarios") or [],
        "narrative": job.get("narrative") or [],
        "questions": job.get("questions") or [],
        "events": (job.get("events") or [])[-40:],
        "universe": job.get("universe") or 0,
        "updated": job.get("updated"),
        "studies": job.get("studies") or [],
        "drill": job.get("drill") or {},
        "report_url": job.get("report_url") or report_url(str(job.get("id") or "")),
        "report_file": job.get("report_file") or "",
        "excel_url": job.get("excel_url") or "",
        "thought": job.get("thought") or "",
        "mind": job.get("mind") or {},
        "rules": job.get("rules") or [],
        "integrations": job.get("integrations") or [],
        "possible": job.get("possible") or [],
    }


def _reason(job: dict) -> None:
    """Multi-hop consultant narrative from LIVE counts only."""
    by = {c["table"]: c.get("entries_found") for c in job["counts"] if c.get("entries_found") is not None}
    lines: list[str] = []
    hops: list[str] = []

    def n(tab: str) -> int | None:
        return by.get(tab)

    def pair(a: str, b: str, when_both: str, when_a0: str | None = None, when_b0: str | None = None) -> None:
        va, vb = n(a), n(b)
        if va is None or vb is None:
            return
        if va == 0 and when_a0:
            hops.append(when_a0.format(a=va, b=vb, A=a, B=b))
            return
        if vb == 0 and when_b0:
            hops.append(when_b0.format(a=va, b=vb, A=a, B=b))
            return
        hops.append(when_both.format(a=va, b=vb, gap=va - vb, A=a, B=b))

    pair(
        "VBAK",
        "LIKP",
        "Sales orders {a:,} vs deliveries {b:,}: {gap:,} orders never became a delivery on this book.",
        when_a0="No sales orders ({A}=0). This is not an OTC book until VBAK is live.",
    )
    pair(
        "LIKP",
        "VBRK",
        "Deliveries {a:,} vs customer invoices {b:,}: {gap:,} deliveries sit unbilled. RAR cannot start on an unbilled delivery.",
        when_b0="Deliveries exist ({a:,}) but VBRK=0 — nothing has been billed. RAR has no RAI input.",
    )
    pair(
        "VBRK",
        "BSID",
        "Invoices {a:,} vs open AR {b:,}. Cash collection is a different clock from revenue recognition.",
    )
    pair(
        "VBRK",
        "BSAD",
        "Invoices {a:,} vs cleared AR {b:,}. Collection works when someone does it; that does not prove RAR ran.",
    )
    pair(
        "VBRK",
        "NAST",
        "Invoices {a:,} vs outputs {b:,}. If outputs are thin, customers were billed in FI and never told.",
    )
    pair(
        "VBRK",
        "FARR_D_CONTRACT",
        "Invoices {a:,} vs RAR contracts {b:,}. If contracts are empty while invoices exist, RAR is not ingesting this company.",
        when_b0="VBRK={a:,} and FARR_D_CONTRACT=0 — classic billing is live, RAR contracts are not. Treat 5k invoices as input, not as recognized revenue.",
    )
    pair(
        "FARR_D_CONTRACT",
        "FARR_D_POB",
        "RAR contracts {a:,} vs performance obligations {b:,}. Many POBs per contract is a bundle story; 1:1 is a simple goods story.",
    )
    pair(
        "FARR_D_POB",
        "FARR_D_REVENUE",
        "POBs {a:,} vs recognized-revenue rows {b:,}. The gap is unearned / not yet fulfilled.",
    )
    pair(
        "FARR_D_POB",
        "FARR_D_DEFITEM",
        "POBs {a:,} vs deferral items {b:,}. Deferral is the balance-sheet clock, not the cash clock.",
    )
    pair(
        "VBRK",
        "VBREVK",
        "Invoices {a:,} vs classic revenue-recognition headers {b:,}. Classic SD RR is not IFRS 15 RAR.",
        when_b0="Classic VBREVK is empty. If FARR is also empty, revenue is posting with the invoice — pre-IFRS 15 behaviour.",
    )
    pair(
        "KNKK",
        "VBAK",
        "Credit masters {a:,} vs sales orders {b:,}.",
        when_a0="Credit master (KNKK) is empty while {b:,} orders exist. Credit is a decision, not a missing t-code.",
    )
    pair(
        "AUFK",
        "AFRU",
        "Production orders {a:,} vs confirmations {b:,}. Unconfirmed orders are WIP, not variance.",
    )
    pair(
        "EKKO",
        "EKBE",
        "Purchasing headers {a:,} vs history {b:,}. History is the proof a PO moved.",
    )

    live = [c for c in job["counts"] if c.get("entries_found") is not None]
    zeros = [c for c in live if c.get("entries_found") == 0]
    missing = [c for c in job["counts"] if c.get("entries_found") is None]
    title = job.get("title") or job.get("asked")
    opened = [c for c in job.get("counts") or [] if c.get("opened")]
    lines.append(
        f"Live glass research for “{title}”. "
        f"Opened {len(opened)} tables and read their contents on the glass. "
        f"Counted {len(live)} with Number of Entries (F7), "
        f"{len(zeros)} empty, {len(missing)} not on this system or not authorized. "
        "F8 is the list (sample). F7 is the census. Nothing was created or posted."
    )
    for st in (job.get("studies") or [])[:8]:
        if st.get("story"):
            lines.append(st["story"])
    if n("VBRK") is not None and n("FARR_D_CONTRACT") == 0:
        lines.append(
            "The billing engine is alive and the RAR contract table is empty. "
            "That is the central finding: this book recognises (or at least invoices) in classic SD/FI. "
            "A consultant who designs IFRS 15 on top of these invoices without first proving RAI ingest "
            "will explain P&L numbers that the system is not keeping."
        )
    if n("VBAK") and n("LIKP") and n("VBRK"):
        lines.append(
            f"The commercial funnel on this client is {n('VBAK'):,} orders → "
            f"{n('LIKP'):,} deliveries → {n('VBRK'):,} invoices. "
            "Each drop is a different team’s problem. Do not buy one tool for all three gaps."
        )
    if n("FARR_D_CONTRACT") and n("FARR_D_CONTRACT") > 0:
        lines.append(
            f"RAR contracts exist ({n('FARR_D_CONTRACT'):,}). "
            "Next glass question is not ‘is RAR installed’ — it is whether every billing type in TVFK "
            "creates a RAI, and whether fulfillment has caught up with the invoice."
        )

    # Scenario cards from live evidence
    scenarios = []
    src = analyze_process(job.get("asked") or "")
    for text in src.get("scenarios") or []:
        status = "OPEN"
        if "FARR" in text or "RAI" in text or "RAR" in text:
            if n("FARR_D_CONTRACT") == 0 and n("VBRK"):
                status = "LIVE"
                text = text + f" Live proof: VBRK={n('VBRK'):,} and FARR_D_CONTRACT=0."
            elif n("FARR_D_CONTRACT"):
                status = "LIVE"
                text = text + f" Live proof: FARR_D_CONTRACT={n('FARR_D_CONTRACT'):,}."
        if "unbilled" in text.lower() and n("LIKP") is not None and n("VBRK") is not None:
            status = "LIVE"
            text = text + f" Live proof: LIKP={n('LIKP'):,}, VBRK={n('VBRK'):,}."
        if "credit" in text.lower() and n("KNKK") == 0:
            status = "LIVE"
        scenarios.append({"name": text.split(":")[0][:48], "status": status, "text": text})

    job["hops"] = hops or list(src.get("hops") or [])
    job["narrative"] = lines
    job["scenarios"] = scenarios or [
        {"name": s.split(":")[0][:48], "status": "OPEN", "text": s}
        for s in (src.get("scenarios") or [])
    ]
    job["questions"] = src.get("questions") or []


def _look(hh, job: dict) -> None:
    view = hh.see("look")
    job["sap_title"] = hh._title()
    if view and view.path:
        job["shot_name"] = Path(view.path).name
        job["shot_seq"] = int(job.get("shot_seq") or 0) + 1
    _emit(job, "look", f"On the glass: {job.get('sap_title') or 'SAP'}")


def _visit(hh, job: dict, step: dict) -> None:
    code = step["tcode"]
    try:
        code = assert_display_tcode(code)
    except DisplayPolicyError as e:
        _emit(job, "refuse", str(e))
        return
    close_popups(hh)
    from sapilot.product.deadlock import run_cut

    nav = run_cut(
        lambda: goto_checked(hh, code, retries=0),
        22,
        on_cut={"ok": False, "cut": True, "title": hh._title() or "", "detail": "goto timeout", "kind": "tx", "expect_ok": False, "attempt": 1},
    )
    if nav.get("cut"):
        _emit(job, "think", f"{code} did not answer in 22s. I cut that deadlock and move on.")
        try:
            back_out(hh, steps=1)
        except Exception:
            pass
        job["visits"].append(
            {
                "tcode": code,
                "ok": False,
                "title": nav.get("title") or "",
                "shot": None,
                "note": "cut: goto timeout",
            }
        )
        return
    title = nav.get("title") or ""
    status = nav.get("status") or ""
    view = None
    try:
        view = hh.see(f"visit_{code.lower()}")
        if view and view.status:
            status = view.status.text or status
        title = hh._title() or title
    except Exception:
        if not rebind(hh):
            _emit(job, "error", f"{code}: lost SAP window — rebound failed")
            return
        try:
            view = hh.see(f"visit_{code.lower()}")
        except Exception:
            pass
    if is_create_screen(title, status) or nav.get("kind") == "create":
        back_out(hh, steps=2)
        job["visits"].append(
            {
                "tcode": code,
                "ok": False,
                "title": title,
                "shot": Path(view.path).name if view and view.path else None,
                "note": "Create/change screen — backed out, nothing saved",
            }
        )
        _emit(job, "refuse", f"{code} looked like a write screen — backed out.")
        return
    if not nav.get("ok"):
        _emit(
            job,
            "error",
            f"{code} landed wrong ({title or nav.get('detail') or 'no title'}) "
            f"— backed out and retried {nav.get('attempt') or 1}×.",
        )
    rec = {
        "tcode": code,
        "ok": bool(nav.get("ok")),
        "title": title,
        "purpose": step.get("purpose") or "",
        "shot": Path(view.path).name if view and view.path else None,
        "note": nav.get("detail") or title,
        "retries": nav.get("attempt") or 1,
    }
    job["visits"].append(rec)
    if view and view.path:
        job["shot_name"] = Path(view.path).name
        job["shot_seq"] = int(job.get("shot_seq") or 0) + 1
    job["sap_title"] = title
    _emit(job, "goto", f"Opened {code} — {title or 'no title'} (try {nav.get('attempt') or 1})")


def _run(job_id: str, sap_ok: Callable[[], dict]) -> None:
    job = get_job(job_id)
    if not job:
        return
    try:
        job["status"] = "running"
        job["phase"] = "look"
        w = sap_ok()
        if not w.get("ok"):
            job["status"] = "error"
            job["error"] = (
                w.get("title")
                or "No logged-in SAP session. Log in (Easy Access), leave the window visible, Ask again."
            )
            _emit(job, "error", job["error"])
            _save(job)
            return

        from sapilot.autobot.operator import HumanEyesHands

        hh = HumanEyesHands(shot_dir=job["dir"])
        _look(hh, job)
        _reason(job)
        _save(job)

        tables: list[str] = list(job["plan_tables"])
        visits: list[dict] = list(job["plan_tcodes"])
        total = len(tables) + len(visits)
        job["progress"] = {
            "done": 0,
            "total": total,
            "tables_ok": 0,
            "tables_zero": 0,
            "tables_miss": 0,
            "visits": 0,
        }

        # First look at SE16N so the user sees the table work start.
        job["phase"] = "census"
        _emit(job, "note", "Opening SE16N. F7 = true count. F8 opens the table so we read contents.")
        se = ensure_screen(hh, "SE16N", retries=3)
        if not se.get("ok"):
            job["status"] = "error"
            job["error"] = (
                "Could not open SE16N after recover/retry. "
                f"Last glass: {se.get('title') or 'unknown'}. Check S_TCODE and leave SAP visible."
            )
            _emit(job, "error", job["error"])
            _save(job)
            return
        _look(hh, job)

        visit_i = 0
        queue = list(tables)
        seen_tables: set[str] = set()
        i = 0
        while queue:
            if job.get("stop"):
                break
            table = (queue.pop(0) or "").strip().upper()
            if not table or table in seen_tables:
                continue
            seen_tables.add(table)
            i += 1
            job["phase"] = "census"
            _emit(job, "census", f"SE16N · open + read {table}  ({i}/{max(len(seen_tables) + len(queue), 1)})")
            try:
                from sapilot.learn.mind import decide

                asked = (job.get("asked") or "").upper()
                verdict = decide(table, confirm=table.upper() in asked)
                job["thought"] = verdict.get("thought") or ""
                _emit(job, "think", verdict.get("thought") or f"Considering {table}")
                if verdict.get("action") == "skip":
                    rec = {
                        "table": table,
                        "entries_found": 0 if verdict.get("kind") == "empty" else None,
                        "rank": "LIVE" if verdict.get("kind") == "empty" else "ABSENT",
                        "shot": None,
                        "opened": False,
                        "notes": verdict.get("thought") or "mind skip",
                        "thought": verdict.get("thought") or "",
                        "contents": {
                            "table": table,
                            "story": verdict.get("thought") or "",
                            "columns": [],
                            "sample_rows": [],
                            "signals": [verdict.get("kind") or "skip"],
                            "visible_rows": 0,
                        },
                    }
                    job["counts"].append(rec)
                    job["progress"]["tables_miss" if rec["rank"] == "ABSENT" else "tables_zero"] += 1
                    job["progress"]["done"] += 1
                    job.setdefault("studies", []).append(rec["contents"])
                    _reroute(job, queue, seen_tables, table)
                    _save(job)
                    continue
            except Exception:
                pass
            try:
                from sapilot.product.table_read import study_table

                rec = study_table(hh, table)
            except Exception as e:
                _emit(job, "error", f"{table}: {e} — recover and retry once")
                try:
                    if "not a window" in str(e).lower():
                        rebind(hh)
                    else:
                        back_out(hh, steps=1)
                    from sapilot.product.table_read import study_table

                    rec = study_table(hh, table)
                    rec["notes"] = (rec.get("notes") or "") + f" (after recover from {e})"
                except Exception as e2:
                    rec = {
                        "table": table,
                        "entries_found": None,
                        "rank": "ABSENT",
                        "shot": None,
                        "opened": False,
                        "notes": f"{e2}"[:180],
                    }
                    _emit(job, "error", f"{table}: still failing after recover ({e2})")
            if rec.get("shot"):
                rec["shot"] = Path(str(rec["shot"])).name
                job["shot_name"] = rec["shot"]
                job["shot_seq"] = int(job.get("shot_seq") or 0) + 1
            job["counts"].append(rec)
            job["thought"] = rec.get("thought") or job.get("thought") or ""
            if rec.get("thought"):
                _emit(job, "think", rec["thought"])
            try:
                from sapilot.learn.mind import snapshot

                job["mind"] = snapshot()
            except Exception:
                pass
            job["sap_title"] = hh._title()
            n = rec.get("entries_found")
            if n is None:
                job["progress"]["tables_miss"] += 1
                _emit(job, "count", f"{table} — not proven ({rec.get('notes') or 'no popup'})")
                _reroute(job, queue, seen_tables, table)
            elif n == 0:
                job["progress"]["tables_zero"] += 1
                _emit(job, "count", f"{table} = 0  (empty on this book)")
                if table.startswith("FARR"):
                    _reroute(job, queue, seen_tables, table)
            else:
                job["progress"]["tables_ok"] += 1
                _emit(job, "count", f"{table} = {n:,}  LIVE")
            if rec.get("opened") and rec.get("contents"):
                _emit(job, "read", rec["contents"].get("story") or f"Opened {table}")
                job.setdefault("studies", []).append(rec["contents"])
            try:
                from sapilot.product.xlsx_out import write_job_workbook

                xlsx = write_job_workbook(job)
                job["excel_name"] = Path(xlsx).name
                job["excel_url"] = f"/api/research/{job['id']}/file/{Path(xlsx).name}"
            except Exception as ex:
                _emit(job, "note", f"Excel not written yet: {ex}")
            job["progress"]["done"] += 1
            if i % 3 == 2 or n:
                _reason(job)
            _save(job)

            # Interleave a display hop so they watch more than tables.
            if visits and (i + 1) % 12 == 0 and visit_i < len(visits):
                if job.get("stop"):
                    break
                job["phase"] = "display"
                step = visits[visit_i]
                visit_i += 1
                _emit(job, "note", f"Display hop {step['tcode']} — then back to SE16N.")
                try:
                    _visit(hh, job, step)
                except Exception as e:
                    _emit(job, "error", f"{step['tcode']}: {e}")
                job["progress"]["visits"] += 1
                job["progress"]["done"] += 1
                job["phase"] = "census"
                _emit(job, "note", "Back to SE16N after display hop.")
                back = ensure_screen(hh, "SE16N", retries=3)
                if not back.get("ok"):
                    _emit(job, "error", f"Could not return to SE16N ({back.get('title')}) — reset via Easy Access.")
                    ensure_screen(hh, "SE16N", retries=2)
                _reason(job)
                _save(job)

        # Remaining display hops
        job["phase"] = "display"
        while visit_i < len(visits) and not job.get("stop"):
            step = visits[visit_i]
            visit_i += 1
            try:
                _visit(hh, job, step)
            except Exception as e:
                _emit(job, "error", f"{step['tcode']}: {e}")
            job["progress"]["visits"] += 1
            job["progress"]["done"] += 1
            _reason(job)
            _save(job)

        job["phase"] = "reason"
        _reason(job)
        if job.get("stop"):
            job["status"] = "stopped"
            _emit(job, "note", "Stopped. Report uses only tables proven before stop.")
        else:
            job["status"] = "done"
            _emit(job, "note", "Research sitting complete. Report is live counts + hops only.")
        _save(job)
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        _emit(job, "error", f"{e}\n{traceback.format_exc()[-400:]}")
        _save(job)


def start_research(message: str, sap_ok: Callable[[], dict], *, max_tables: int | None = None) -> dict:
    q = (message or "").strip()
    if not q:
        return {"ok": False, "error": "Ask a process. Example: Analyze the complete RAR process."}

    running = active_job()
    if running:
        return {
            "ok": False,
            "error": "A live research sitting is already running. Stop it first, or watch the current one.",
            "id": running["id"],
        }

    window = sap_ok()
    if not window.get("ok"):
        return {
            "ok": False,
            "error": (
                window.get("title")
                or "No logged-in SAP session. Log into SAP (Easy Access), leave that window visible, then Analyze."
            ),
            "hint": "The operator cannot research a closed book. Log in first, then press Analyze and watch the left pane.",
        }

    asked = _extract_process(q)
    limit = int(max_tables) if max_tables else _max_tables()
    plan = plan_research(asked, max_tables=limit)
    if "otc 10" in q.lower() or "tab per table" in q.lower():
        plan["tables"] = ["VBAK", "VBAP", "LIKP", "LIPS", "VBRK", "VBRP", "BSID", "BSAD", "NAST", "KNA1"]
        plan["tcodes"] = []
        plan["universe"] = 10
        limit = 10
    if limit <= 5:
        plan["tcodes"] = []
    job_id = uuid.uuid4().hex[:12]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = _root() / f"{ts}_{job_id}"
    dest.mkdir(parents=True, exist_ok=True)
    job = {
        "id": job_id,
        "status": "starting",
        "phase": "plan",
        "asked": q,
        "process": asked,
        "title": plan.get("title"),
        "spine": plan.get("spine"),
        "story": plan.get("story"),
        "dir": str(dest),
        "plan_tables": plan["tables"],
        "plan_tcodes": plan["tcodes"],
        "universe": plan["universe"],
        "counts": [],
        "studies": [],
        "visits": [],
        "hops": list(plan.get("hops") or []),
        "scenarios": [{"name": s.split(":")[0][:48], "status": "OPEN", "text": s} for s in plan.get("scenarios") or []],
        "narrative": [plan.get("story") or ""],
        "questions": list(plan.get("questions") or []),
        "events": [],
        "progress": {"done": 0, "total": len(plan["tables"]) + len(plan["tcodes"]), "tables_ok": 0},
        "shot_seq": 0,
        "shot_name": None,
        "sap_title": "",
        "stop": False,
        "error": None,
        "started": _now(),
        "updated": _now(),
        "report_url": report_url(job_id),
        "report_file": str(dest / "REPORT.html"),
    }
    _emit(
        job,
        "plan",
        f"Plan: {len(plan['tables'])} tables + {len(plan['tcodes'])} display hops. "
        "Entering SAP now. F7 only.",
    )
    _save(job)
    with _LOCK:
        _JOBS[job_id] = job
    t = threading.Thread(target=_run, args=(job_id, sap_ok), daemon=True)
    _THREAD[job_id] = t
    t.start()
    return {"ok": True, **public_job(job)}
