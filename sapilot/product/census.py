"""SE16N Number of Entries (F7). Never F8 / never a 500-row list as a count."""
from __future__ import annotations

import re
import time
from typing import Any

from sapilot.autobot.eyes import find_label, ocr_text
from sapilot.autobot.operator import HumanEyesHands
from sapilot.autobot.vision_operator import Op, find_popup
from sapilot.product.navigate import (
    back_out,
    classify,
    dismiss,
    ensure_screen,
    rebind,
    screen_text,
)


def parse_entries(text: str) -> int | None:
    blob = (text or "").replace(",", "").replace("\u00a0", " ")
    m = re.search(r"entries\s+found\s*[:\-]?\s*(\d+)", blob, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"found\s*[:\-]?\s*(\d+)", blob, re.I)
    return int(m.group(1)) if m else None


def close_popups(hh: HumanEyesHands) -> None:
    dismiss(hh)
    op = hh._op()
    for title in ("Entries", "Number of", "Technical Settings", "Messages"):
        pop = find_popup(title, exclude=op.hwnd)
        if not pop:
            continue
        popop = Op(hwnd=pop, shot_dir=hh.shot_dir)
        popop.click(0.97, 0.16, settle=0.2)
        time.sleep(0.2)


def ensure_se16n(hh: HumanEyesHands) -> bool:
    rec = ensure_screen(hh, "SE16N", retries=2)
    return bool(rec.get("ok"))


def _focus_database(hh: HumanEyesHands, view) -> None:
    """Click the Data base field. Prefer a learned click; never the ALV cell."""
    try:
        from sapilot.learn.policy import apply, suggest

        title = hh._title() or ""
        blob = " ".join(w.text for w in (view.words or [])) if view else ""
        action = suggest(title, "", blob, "focus_database")
        if action and action.get("kind") == "click":
            apply(hh, action)
            time.sleep(0.12)
            return
    except Exception:
        pass
    hit = None
    if view is not None:
        hit = find_label(view.words, ["Data base", "Database"])
    if hit is not None and 0.16 <= hit.ry <= 0.38:
        hh.click_frac(min(0.40, hit.rx + 0.11), hit.ry)
    else:
        # Belize SE16N: field sits under the toolbar, left of the description.
        hh.click_frac(0.30, 0.248)
    time.sleep(0.12)


def _wrong_field(status: str, blob: str, table: str) -> bool:
    rec = classify("", status, blob, expect="SE16N")
    if rec.get("retry"):
        return True
    low = f"{status} {blob}".lower()
    if "is not created in language" in low:
        return True
    if "unit " in low and table.upper()[:3] in (status or "").upper():
        return True
    return False


def _table_on_glass(blob: str, status: str, table: str) -> bool:
    name = table.upper().replace(" ", "")
    blob_u = (blob + " " + status).upper().replace(" ", "")
    return name in blob_u


def load_table(hh: HumanEyesHands, table: str) -> tuple[bool, str]:
    name = (table or "").strip().upper()
    hh.see(f"{name.lower()}_before")
    filled = hh.fill_se16n_table(name)
    tech = find_popup("Technical Settings", exclude=hh._op().hwnd)
    if tech:
        Op(hwnd=tech, shot_dir=hh.shot_dir).click(0.97, 0.16, settle=0.25)
        time.sleep(0.25)
        hh.key("ESCAPE", settle=0.25)
    view = hh.see(f"{name.lower()}_sel")
    blob = " ".join(w.text for w in (view.words or []))
    status = (view.status.text if view.status else "") or ""
    if not filled.ok and filled.detail:
        status = status or filled.detail
        blob = f"{blob} {filled.detail}"
    from sapilot.product.sap_status import assess_load, note_missing_table

    rec = assess_load(status, blob, name)
    try:
        from sapilot.learn.mind import observe as mind_observe

        mind_observe(name, status=status, blob=blob, notes=rec.get("text") or "")
    except Exception:
        pass
    if rec["kind"] == "missing_table" or rec["kind"] == "leftover":
        note_missing_table(name, rec["text"])
        why = rec["text"][:80]
        if rec.get("leftover"):
            why = f"{why} leftover={rec['leftover']}"
        return False, f"table does not exist ({why})"
    if rec["kind"] == "auth":
        return False, f"not authorized ({rec['text'][:80]})"
    if rec["fatal"]:
        return False, rec["text"][:180] or "status-bar error"
    if _wrong_field(status, blob, name):
        return False, f"typed into the wrong field ({(status or blob)[:120]})"
    # Typed name in Data base is not a load. Leftover Fld Name / MANDT from the
    # previous table is not a load. Only a non-fatal, non-leftover catalog is.
    if rec["loaded"]:
        try:
            from sapilot.learn.policy import remember

            remember(
                hh._title() or "",
                status,
                blob,
                "focus_database",
                {"kind": "fill_se16n", "table": name},
                1,
                note=name,
            )
        except Exception:
            pass
        return True, (status or blob)[:180]
    try:
        from sapilot.learn.policy import remember

        remember(
            hh._title() or "",
            status,
            blob,
            "focus_database",
            {"kind": "fill_se16n", "table": name},
            -1,
            note=name,
        )
    except Exception:
        pass
    return False, (status or blob)[:180] or "table name not proven on glass"


def count_table(hh: HumanEyesHands, table: str) -> dict[str, Any]:
    """F7 Number of Entries. Recover + retry on nav errors. Never F8."""
    last_note = ""
    for attempt in range(3):
        try:
            close_popups(hh)
            if not ensure_se16n(hh):
                last_note = "SE16N not on the glass"
                if attempt < 2:
                    back_out(hh, steps=1)
                    continue
                return {
                    "table": table,
                    "entries_found": None,
                    "rank": "ABSENT",
                    "shot": None,
                    "notes": last_note,
                    "retries": attempt,
                }
            close_popups(hh)
            loaded, note = load_table(hh, table)
            last_note = note
            if not loaded:
                if note.startswith("table does not exist"):
                    shot = hh.see(f"{table.lower()}_miss")
                    return {
                        "table": table,
                        "entries_found": None,
                        "rank": "ABSENT",
                        "shot": str(shot.path) if shot else None,
                        "notes": note,
                        "retries": attempt,
                    }
                # Wrong field / leftover table (TKA03, Unit VBA) — reset SE16N and retry.
                try:
                    hh.key("ESCAPE", settle=0.3)
                except Exception:
                    pass
                back_out(hh, steps=1)
                ensure_se16n(hh)
                continue

            hh.key("F7", settle=0.7)
            pop = None
            status_zero = False
            unauthorized = False
            for i in range(24):
                time.sleep(0.32)
                pop = find_popup("Entries", exclude=hh._op().hwnd) or find_popup(
                    "Number of", exclude=hh._op().hwnd
                )
                if pop:
                    break
                if i >= 3:
                    probe = hh.see(f"{table.lower()}_probe")
                    st = (probe.status.text if probe.status else "") or ""
                    blob = " ".join(w.text for w in (probe.words or [])) + " " + st
                    low = blob.lower()
                    if "no values found" in low:
                        status_zero = True
                        break
                    if any(x in low for x in ("not authorized", "no authorization", "you are not")):
                        unauthorized = True
                        break
                    if _wrong_field(st, blob, table):
                        last_note = f"F7 hit a nav error ({st[:80]})"
                        break
            rec_shot = None
            n = None
            notes = note
            rank = "LIVE"
            try:
                from PIL import Image
            except Exception:
                Image = None  # type: ignore
            if pop:
                popop = Op(hwnd=pop, shot_dir=hh.shot_dir)
                pshot = popop.screenshot(f"{table.lower()}_popup")
                rec_shot = str(pshot)
                if Image is not None:
                    pop_ocr = ocr_text(Image.open(pshot))
                    n = parse_entries(pop_ocr)
                    notes = (pop_ocr or "").strip()[:180]
                close_popups(hh)
            else:
                view = hh.see(f"{table.lower()}_count")
                rec_shot = str(view.path) if view else None
                blob = ""
                if view:
                    blob = " ".join(w.text for w in (view.words or []))
                    if view.status:
                        blob += " " + (view.status.text or "")
                n = parse_entries(blob)
                if n is None and status_zero:
                    n = 0
                    notes = "No values found (status) after table name proven"
                elif unauthorized:
                    rank = "ABSENT"
                    notes = "Not authorized to read this table"
                elif n is None:
                    if _wrong_field("", blob, table):
                        last_note = (blob[:160] if blob else "nav error after F7")
                        hh.key("ESCAPE", settle=0.3)
                        ensure_se16n(hh)
                        continue
                    rank = "ABSENT"
                    notes = (blob[:180] if blob else "F7 produced no Number of Entries popup")
            if n == 0:
                rank = "ABSENT" if unauthorized else "LIVE"
            return {
                "table": table,
                "entries_found": n,
                "rank": rank if n is not None else "ABSENT",
                "shot": rec_shot,
                "notes": notes or "",
                "retries": attempt,
            }
        except Exception as e:
            last_note = str(e)[:180]
            if "not a window" in last_note.lower() or "session" in last_note.lower():
                if not rebind(hh):
                    break
            else:
                try:
                    back_out(hh, steps=1)
                except Exception:
                    rebind(hh)
    return {
        "table": table,
        "entries_found": None,
        "rank": "ABSENT",
        "shot": None,
        "notes": last_note or "gave up after recover/retry",
        "retries": 3,
    }
