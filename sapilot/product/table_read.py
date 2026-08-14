"""Open an SE16N table and analyze the rows on the glass.

F7 is the true count. F8 opens the list so we can read contents.
A 500-row page is a sample, never the census.
"""
from __future__ import annotations

import time
from collections import Counter
from typing import Any

from sapilot.autobot.eyes import find_label
from sapilot.autobot.operator import HumanEyesHands
from sapilot.product.census import close_popups, count_table

_MEANING = {
    "VBAK": "Sales order headers — what was sold, by which org, which type.",
    "VBAP": "Sales order items — material, qty, plant on each line.",
    "LIKP": "Delivery headers — whether goods left the building.",
    "LIPS": "Delivery items.",
    "VBRK": "Billing headers — the invoice, not yet IFRS 15 revenue.",
    "VBRP": "Billing items.",
    "VBFA": "Document flow — which order became which delivery/bill.",
    "BSID": "Open customer items — cash still owed.",
    "BSAD": "Cleared customer items — cash already collected.",
    "KNA1": "Customer general master.",
    "KNVV": "Customer sales area.",
    "KNKK": "Classic credit master.",
    "T001": "Company codes on this client.",
    "T001W": "Plants.",
    "TVAK": "Sales document types configured.",
    "TVFK": "Billing types configured.",
    "EKKO": "Purchasing document headers.",
    "EKPO": "Purchasing items.",
    "BKPF": "FI document headers.",
    "BSEG": "FI line items.",
    "MARA": "Material general.",
    "FARR_D_CONTRACT": "RAR contracts.",
    "FARR_D_POB": "RAR performance obligations.",
    "FARR_D_REVENUE": "RAR recognized revenue rows — earned POB posted or scheduled to FI.",
    "FARR_D_DEFITEM": "RAR deferral items — unearned balance-sheet clock.",
    "FARR_D_FULFILL": "RAR fulfillment events.",
    "NAST": "Output / messages actually created.",
    "DD02L": "SAP table directory — which tables this dictionary actually has.",
    "VBREVE": "Classic SD revenue recognition lines (not IFRS 15 RAR).",
    "VBREVK": "Classic SD revenue recognition headers.",
    "VBREVR": "Classic SD revenue recognition reference.",
}


def words_to_rows(words, *, min_y: float = 0.18, max_y: float = 0.88) -> list[list[str]]:
    buckets: dict[float, list] = {}
    for w in words or []:
        try:
            if w.ry < min_y or w.ry > max_y:
                continue
            if w.in_chrome():
                continue
        except Exception:
            continue
        text = (w.text or "").strip()
        if not text or text in {"|", "<>", "S|"}:
            continue
        key = round(w.ry * 36) / 36
        buckets.setdefault(key, []).append(w)
    rows: list[list[str]] = []
    for key in sorted(buckets):
        cells = [x.text.strip() for x in sorted(buckets[key], key=lambda z: z.x) if (x.text or "").strip()]
        if cells:
            rows.append(cells)
    return rows


def analyze_grid(table: str, rows: list[list[str]], count: int | None) -> dict[str, Any]:
    """Consultant reading of the open list — not a field dump."""
    blob = " ".join(" ".join(r) for r in rows).lower()
    if "no values found" in blob:
        meaning = _MEANING.get(table.upper(), table)
        return {
            "table": table,
            "story": f"{table} was executed (F8). Status: No values found — the table exists and is empty. {meaning}",
            "columns": [],
            "sample_rows": [],
            "signals": ["F8 ran. Zero rows."],
            "visible_rows": 0,
        }
    if not rows:
        return {
            "table": table,
            "story": f"{table} opened but no row text could be read on this glass.",
            "columns": [],
            "sample_rows": [],
            "signals": [],
        }
    header = rows[0]
    body = rows[1:16]
    # Distinct tokens that look like org / type keys
    tokens: list[str] = []
    for row in body:
        for cell in row:
            if 2 <= len(cell) <= 10 and cell.replace("-", "").isalnum():
                tokens.append(cell)
    common = [f"{k} ×{v}" for k, v in Counter(tokens).most_common(8) if v >= 2]
    meaning = _MEANING.get(table.upper(), f"{table} — document or config table on this process.")
    n = count
    visible = len(body)
    if n is None:
        scale = f"Read {visible} data rows on the glass. True Number of Entries was not proven."
    elif n == 0:
        scale = "Table is empty on this book (F7 = 0). The list should be blank."
    elif visible and n > visible:
        scale = (
            f"F7 count is {n:,}. This screen shows {visible} rows — a sample, not the whole table. "
            "Do not treat 500 list hits as the census."
        )
    else:
        scale = f"F7 count is {n:,}. The open list is enough to see the whole table."
    signals = [meaning, scale]
    if common:
        signals.append("Repeated values on this page: " + ", ".join(common))
    if table.upper() == "T001" and body:
        signals.append("These rows are the company codes this client actually has. Design starts here.")
    if table.upper() == "VBAK" and n:
        signals.append("Each header row is a commercial promise. Next hop is delivery (LIKP), then bill (VBRK).")
    if table.upper().startswith("FARR") and n == 0:
        signals.append("RAR table opened and is empty — classic SD/FI can still be full. Two clocks.")
    return {
        "table": table,
        "story": " ".join(signals),
        "columns": header[:24],
        "sample_rows": body[:12],
        "signals": signals,
        "visible_rows": visible,
    }


def _blob(view) -> str:
    if view is None:
        return ""
    text = " ".join(w.text for w in (view.words or []))
    if view.status:
        text += " " + (view.status.text or "")
    return text


def _on_selection(blob: str) -> bool:
    low = (blob or "").lower()
    return "selection criteria" in low or ("data base" in low and "fld name" in low.replace(".", ""))


def _executed(blob: str, rows: list[list[str]]) -> bool:
    """True only if F8 actually ran: empty result or a list, not the selection dynpro."""
    low = (blob or "").lower()
    if "no values found" in low:
        return True
    if _on_selection(blob):
        return False
    return len(rows) >= 3


def lift_hit_limit(hh: HumanEyesHands, n: int = 200) -> str:
    """Set Max. Number of Hits so the ALV actually paints. F7 is the census."""
    view = hh.see("hits_before")
    from sapilot.autobot.eyes import click_point_for_label

    hit = find_label(view.words, ["Hits:", "Hits"])
    if hit is not None and 0.28 <= hit.ry <= 0.45:
        rx = min(0.28, hit.right_rx + 0.04)
        hh.click_frac(rx, hit.ry)
    else:
        hh.click_frac(0.205, 0.342)
    time.sleep(0.1)
    from sapilot.connect.hwnd_input import send_key_name, send_text_unicode

    for _ in range(12):
        send_key_name("BACK")
    send_text_unicode(str(int(n)))
    send_key_name("ENTER")
    time.sleep(0.4)
    return f"max_hits={int(n)}"


def _click_label(hh, view, aliases: list[str]) -> bool:
    from sapilot.autobot.eyes import click_point_for_label

    hit = find_label(view.words, aliases)
    if hit is None:
        return False
    rx, ry = click_point_for_label(hit, side="on")
    hh.click_frac(rx, ry)
    time.sleep(1.5)
    return True


def open_and_read(hh: HumanEyesHands, table: str) -> dict[str, Any]:
    """Remove 500 cap, then try several execute methods until the list is on the glass."""
    from sapilot.learn.policy import remember, suggest
    from sapilot.product.sap_status import assess_load, note_missing_table

    close_popups(hh)
    peek = hh.see(f"{table.lower()}_pre_exec")
    msg = assess_load(
        peek.status.text if peek and peek.status else "",
        _blob(peek),
        table,
    )
    if msg["fatal"]:
        remember(hh._title() or "", msg["text"], "", "open_list", {"kind": "stop", "reason": msg["kind"]}, 0, note=table)
        if msg["kind"] in {"missing_table", "leftover"}:
            note_missing_table(table, msg["text"])
        return {
            "opened": False,
            "rows": [],
            "blob": msg["text"],
            "shot": str(peek.path) if peek and peek.path else None,
            "how": f"stopped:{msg['kind']}",
            "error": msg["kind"],
        }

    how_limit = lift_hit_limit(hh)
    close_popups(hh)

    # One Execute. If it fails, that is a finding — a second F8 is the same mistake.
    methods = [
        ("f8", lambda v: hh.key("F8", settle=2.0) or True),
    ]
    learned = suggest(hh._title() or "", "", "", "open_list")
    if learned and learned.get("kind") == "key" and learned.get("name") == "F8":
        pass  # already first
    elif learned and learned.get("kind") == "click_label":
        methods.insert(0, ("learned", lambda v: _click_label(hh, v, learned.get("aliases") or ["Online"])))

    view = hh.see(f"{table.lower()}_pre_exec")
    blob = _blob(view)
    rows = words_to_rows(view.words)
    used = []
    for name, fn in methods:
        try:
            ok_click = fn(view)
        except Exception:
            ok_click = False
            remember(hh._title() or "", "", blob, "open_list", {"kind": "method", "name": name}, -1, note=table)
            continue
        if ok_click is False:
            continue
        used.append(name)
        time.sleep(0.4)
        if "entries found" not in (hh._title() or "").lower():
            from sapilot.connect.hwnd_input import send_key_name

            send_key_name("ENTER")
            time.sleep(1.0)
        view = hh.see(f"{table.lower()}_list_{name}")
        blob = _blob(view)
        rows = words_to_rows(view.words)
        after = assess_load(view.status.text if view.status else "", blob, table)
        if after["fatal"]:
            remember(hh._title() or "", after["text"], blob, "open_list", {"kind": "method", "name": name}, -1, note=after["kind"])
            if after["kind"] in {"missing_table", "leftover"}:
                note_missing_table(table, after["text"])
            return {
                "opened": False,
                "rows": rows,
                "blob": after["text"],
                "shot": str(view.path) if view and view.path else None,
                "how": f"stopped:{after['kind']}+{name}",
                "error": after["kind"],
            }
        if _executed(blob, rows) or "entries found" in (hh._title() or "").lower():
            remember(
                hh._title() or "",
                "",
                blob,
                "open_list",
                {"kind": "method", "name": name},
                1,
                note=table,
            )
            break
        remember(hh._title() or "", "", blob, "open_list", {"kind": "method", "name": name}, -1, note=table)
        view = hh.see(f"{table.lower()}_pre_exec")

    extra: list[list[str]] = []
    if _executed(blob, rows) and "no values found" not in blob.lower():
        for i in range(3):
            try:
                hh.key("PAGEDOWN", settle=0.55)
            except Exception:
                break
            more = hh.see(f"{table.lower()}_page{i}")
            extra.extend(words_to_rows(more.words)[1:12])
    if extra:
        rows = rows + extra
    opened = _executed(blob, rows)
    shot = str(view.path) if view and view.path else None
    try:
        hh.key("F3", settle=0.7)
    except Exception:
        pass
    return {
        "opened": opened,
        "rows": rows,
        "blob": blob[:240],
        "shot": shot,
        "how": "+".join(used) + f"+{how_limit}",
    }


def study_table(hh: HumanEyesHands, table: str) -> dict[str, Any]:
    """Load, count (F7), open (F8), read contents, learn from the result."""
    from sapilot.learn.mind import decide, observe

    verdict = decide(table)
    rec: dict[str, Any] = {
        "table": table,
        "opened": False,
        "contents": None,
        "thought": verdict.get("thought") or "",
    }
    if verdict.get("action") == "skip":
        rec.update(
            {
                "entries_found": None if verdict.get("kind") != "empty" else 0,
                "rank": "ABSENT" if verdict.get("kind") != "empty" else "LIVE",
                "shot": None,
                "notes": verdict.get("thought") or "mind skip",
                "contents": {
                    "table": table,
                    "story": verdict.get("thought") or "",
                    "columns": [],
                    "sample_rows": [],
                    "signals": [verdict.get("kind") or "skip"],
                    "visible_rows": 0,
                },
            }
        )
        if verdict.get("kind") == "empty":
            rec["entries_found"] = 0
            rec["rank"] = "LIVE"
        return rec

    rec = count_table(hh, table)
    rec.setdefault("table", table)
    rec["opened"] = False
    rec["contents"] = None
    rec["thought"] = verdict.get("thought") or rec.get("thought") or ""
    notes = rec.get("notes") or ""
    seen = observe(
        table,
        status=notes,
        notes=notes,
        entries=rec.get("entries_found"),
    )
    rec["thought"] = seen.get("thought") or rec.get("thought") or ""
    if notes.startswith("table does not exist") or rec.get("rank") == "ABSENT" and "does not exist" in notes.lower():
        rec["opened"] = False
        rec["contents"] = {
            "table": table,
            "story": (
                f"{table} is not on this dictionary. SAP status: {notes}. "
                "Stopped — will not Execute (F8) a table that does not exist."
            ),
            "columns": [],
            "sample_rows": [],
            "signals": [notes],
            "visible_rows": 0,
        }
        return rec
    # Always Execute (F8) so the list contents are on the glass. F7 is only the count.
    try:
        opened = open_and_read(hh, table)
        rec["opened"] = bool(opened.get("opened"))
        rec["contents"] = analyze_grid(table, opened.get("rows") or [], rec.get("entries_found"))
        if opened.get("shot"):
            rec["list_shot"] = opened["shot"]
        try:
            from sapilot.learn.policy import remember

            remember(
                hh._title() or "",
                "",
                "",
                "open_list",
                {"kind": "key", "name": "F8"},
                1 if rec["opened"] else -1,
                note=table,
            )
        except Exception:
            pass
    except Exception as e:
        rec["notes"] = (rec.get("notes") or "") + f" · open failed: {e}"[:160]
    return rec
