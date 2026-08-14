"""Read the SAP status strip. Fatal errors stop the sitting. Do not retry blindly."""
from __future__ import annotations

import re
from typing import Any


# Other tables' field catalogs. If we asked for X and still see Y's fields,
# ENTER was rejected — do not F7/F8 Y's rows under X's name.
_FINGERPRINTS: dict[str, frozenset[str]] = {
    "T001": frozenset({"BUTXT", "ORT01", "LAND1", "WAABW", "KOKFI", "RCOMP", "WAERS"}),
    "T001W": frozenset({"WERKS", "FABKL", "BWKEY", "NAME1"}),
    "VBAK": frozenset({"AUART", "VKORG", "VTWEG", "SPART", "KUNNR"}),
    "VBRK": frozenset({"FKART", "FKTYP", "WAERK", "KUNRG"}),
    "EKKO": frozenset({"BSART", "LIFNR", "EKORG", "EKGRP"}),
    "FARR_D_CONTRACT": frozenset({"CONTRACT_ID", "CONTRACT_CAT", "ACCT_PRINCIPLE", "CONTR_CREATED_ON"}),
    "FARR_D_POB": frozenset({"POB_ID", "POB_TYPE", "FULFILL_TYPE"}),
}

_TECH = re.compile(r"\b([A-Z][A-Z0-9_]{3,30})\b")


def classify_message(status: str = "", blob: str = "", table: str = "") -> dict[str, Any]:
    """
    kind: missing_table | empty | auth | bad_okcd | wrong_field | leftover | ok
    fatal: stop this table / this method. Do not try F8 four more times.
    """
    text = f"{status} {blob}".lower()
    compact = text.replace(" ", "")
    name = (table or "").strip().lower()
    rec = {"kind": "ok", "fatal": False, "retry": False, "text": (status or blob or "")[:180]}

    if "no values found" in text:
        rec.update(kind="empty", fatal=False)
        return rec
    if (
        "check the name" in text
        or "checkthename" in compact
        or "unknown table" in text
        or "invalid table" in text
    ):
        rec.update(kind="missing_table", fatal=True)
        return rec
    if "does not exist" in text or "doesnotexist" in compact:
        # Name is usually IN the field because we just typed it. That is not a load.
        if not name or name.replace("_", "") in compact.replace("_", "") or name in text:
            rec.update(kind="missing_table", fatal=True)
            return rec
    if "not authorized" in text or "no authorization" in text or "you are not" in text:
        rec.update(kind="auth", fatal=True)
        return rec
    if "invalid ok command" in text or "invalid ok-code" in text:
        rec.update(kind="bad_okcd", fatal=True, retry=True)
        return rec
    if "is not created in language" in text:
        rec.update(kind="wrong_field", fatal=False, retry=True)
        return rec
    return rec


def catalog_tokens(blob: str) -> set[str]:
    return set(_TECH.findall((blob or "").upper()))


def leftover_table(blob: str, asked: str) -> str | None:
    """Return the other table whose field catalog is still on the glass."""
    tokens = catalog_tokens(blob)
    asked_u = (asked or "").strip().upper()
    own = _FINGERPRINTS.get(asked_u)
    if own and len(own & tokens) >= 2:
        return None
    blob_u = (blob or "").upper()
    if asked_u != "T001" and "COMPANY CODES" in blob_u and "BUKRS" in tokens:
        return "T001"
    best: str | None = None
    best_n = 0
    for other, fp in _FINGERPRINTS.items():
        if other == asked_u:
            continue
        n = len(fp & tokens)
        if n >= 3 and n > best_n:
            best, best_n = other, n
    return best


def assess_load(status: str = "", blob: str = "", table: str = "") -> dict[str, Any]:
    """Did SE16N actually load THIS table? Typed name in Data base is not proof."""
    msg = classify_message(status, blob, table)
    leftover = leftover_table(blob, table)
    rec = {
        "kind": msg["kind"],
        "fatal": bool(msg["fatal"]),
        "retry": bool(msg["retry"]),
        "text": msg["text"],
        "loaded": False,
        "leftover": leftover,
    }
    if msg["fatal"]:
        return rec
    if leftover:
        rec.update(
            kind="leftover",
            fatal=True,
            loaded=False,
            text=msg["text"] or f"field catalog is still {leftover}, not {table}",
        )
        return rec
    rec["loaded"] = msg["kind"] in {"ok", "empty"}
    return rec


def note_missing_table(table: str, status: str = "") -> None:
    try:
        from sapilot.learn.memory import default_memory

        name = (table or "").strip().upper()
        default_memory().add_knowledge(
            "glass",
            f"missing_table:{name}",
            {"kind": "missing_table", "table": name, "status": (status or "")[:160]},
        )
    except Exception:
        pass


def is_known_missing(table: str) -> dict[str, Any] | None:
    try:
        from sapilot.learn.memory import default_memory

        name = (table or "").strip().upper()
        for rec in default_memory().knowledge():
            if rec.get("kind") == "missing_table" and (rec.get("table") or "").upper() == name:
                return rec
    except Exception:
        return None
    return None
