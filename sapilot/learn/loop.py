"""Live self-training: practice display navigation, keep what works."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable

from sapilot.learn.ingest import seed
from sapilot.learn.memory import default_memory
from sapilot.learn.policy import apply, remember, suggest
from sapilot.product.navigate import classify, ensure_screen, screen_text

_LOCK = threading.Lock()
_STATE: dict[str, Any] = {"status": "idle", "log": [], "step": ""}


def status() -> dict[str, Any]:
    mem = default_memory()
    with _LOCK:
        st = dict(_STATE)
    st["memory"] = mem.stats()
    st["knowledge"] = [
        {"source": k.get("source"), "title": k.get("title"), "url": k.get("url")}
        for k in mem.knowledge()[:12]
    ]
    try:
        from sapilot.learn.mind import snapshot

        st["mind"] = snapshot(mem)
    except Exception:
        st["mind"] = {}
    return st


def _log(msg: str) -> None:
    with _LOCK:
        _STATE["step"] = msg
        _STATE["log"] = (_STATE.get("log") or [])[-40:] + [msg]


def _practice_once(hh, sap_ok: Callable[[], dict]) -> dict[str, Any]:
    """One autonomous practice lap. Display only. Records every attempt."""
    seed()
    w = sap_ok()
    if not w.get("ok"):
        return {"ok": False, "error": "No logged-in SAP session. Log in, then Practice."}

    drills = [
        ("menu", "SESSION_MANAGER"),
        ("reset_se16n", "SE16N"),
        ("focus_database", None),
        ("open_list", None),
        ("goto", "VA03"),
        ("recover", None),
        ("reset_se16n", "SE16N"),
    ]
    results: list[dict[str, Any]] = []
    for intent, tcode in drills:
        title, status, blob = screen_text(hh)
        rec = classify(title, status, blob, expect=tcode)
        action = suggest(title, status, blob, intent)
        if tcode and (not action or action.get("kind") != "goto"):
            action = {"kind": "goto", "tcode": tcode, "why": "drill"}
        _log(f"{intent}: {action}")
        try:
            apply(hh, action or {"kind": "back_out"})
            time.sleep(0.5)
            t2, s2, b2 = screen_text(hh)
            after = classify(t2, s2, b2, expect=tcode or "SE16N")
            if intent == "open_list":
                from sapilot.learn.mind import observe
                from sapilot.product.sap_status import assess_load

                judged = assess_load(status, blob, "T001")
                if judged["fatal"]:
                    observe("T001", status=status, blob=blob, notes=judged["text"])
                    remember(title, status, blob, intent, {"kind": "stop", "reason": judged["kind"]}, 1, note=judged["text"])
                    results.append({"intent": intent, "ok": True, "detail": "stopped on status: " + judged["kind"]})
                    continue
                from sapilot.product.table_read import study_table

                ct = study_table(hh, "T001")
                win = bool(ct.get("opened") or ct.get("entries_found") is not None)
                remember(title, status, blob, intent, {"kind": "key", "name": "F8"}, 1 if win else -1, note=str((ct.get("contents") or {}).get("story") or ct.get("notes") or ""))
                results.append({"intent": intent, "ok": win, "detail": ct.get("contents") or ct})
                continue
            if intent == "focus_database":
                from sapilot.product.census import load_table

                ok, note = load_table(hh, "T001")
                remember(title, status, blob, intent, action or {}, 1 if ok else -1, note=note)
                results.append({"intent": intent, "ok": ok, "detail": note})
                continue
            win = bool(after.get("expect_ok")) if tcode else after.get("kind") in {"menu", "se16n"}
            if intent == "recover":
                win = after.get("kind") in {"menu", "se16n", "tx"} and after.get("kind") != "create"
            remember(title, status, blob, intent, action or {}, 1 if win else -1, note=t2)
            results.append({"intent": intent, "ok": win, "title": t2})
            if not win:
                ensure_screen(hh, "SE16N" if intent != "menu" else "SESSION_MANAGER", retries=1)
        except Exception as e:
            remember(title, status, blob, intent, action or {}, -1, note=str(e)[:160])
            results.append({"intent": intent, "ok": False, "error": str(e)[:160]})
            _log(f"error {intent}: {e}")
    wins = sum(1 for r in results if r.get("ok"))
    return {"ok": True, "wins": wins, "drills": len(results), "results": results}


def practice(sap_ok: Callable[[], dict], *, laps: int = 1) -> dict[str, Any]:
    with _LOCK:
        if _STATE.get("status") == "running":
            return {"ok": False, "error": "Practice is already running."}
        _STATE["status"] = "running"
        _STATE["log"] = []
    try:
        from sapilot.autobot.operator import HumanEyesHands
        import os
        from pathlib import Path

        root = Path(os.environ.get("SAPILOT_DATA", "data")) / "runs" / "product" / "practice"
        root.mkdir(parents=True, exist_ok=True)
        hh = HumanEyesHands(shot_dir=str(root))
        out: dict[str, Any] = {"ok": True, "laps": []}
        for i in range(max(1, min(int(laps), 3))):
            _log(f"practice lap {i + 1}")
            out["laps"].append(_practice_once(hh, sap_ok))
        out["memory"] = default_memory().stats()
        return out
    finally:
        with _LOCK:
            _STATE["status"] = "idle"
            _STATE["step"] = "idle"
