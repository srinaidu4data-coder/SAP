"""The operator's mind: beliefs from the glass, lessons that stop retries.

This is not a win/loss counter. It is what a person would remember after
looking at SAP: which tables exist, which are empty, which SAP already
rejected, and what to do next. Thoughts are written in English so the
console can show them.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sapilot.learn.memory import NavMemory, default_memory
from sapilot.product.sap_status import assess_load, note_missing_table


LESSONS: list[dict[str, str]] = [
    {
        "id": "read_status",
        "text": "Read the red status strip before F7 or F8. The strip is the truth.",
    },
    {
        "id": "no_f8_missing",
        "text": "If SAP says the table does not exist, stop. Never Execute a rejected name.",
    },
    {
        "id": "leftover_not_load",
        "text": "A typed name plus leftover fields from the previous table is not a load.",
    },
    {
        "id": "f7_count",
        "text": "Number of Entries is F7. F8 opens the list so we can read rows.",
    },
    {
        "id": "lift_500",
        "text": "Lift Max. Number of Hits off 500 before Execute. 500 is a page, not a census.",
    },
    {
        "id": "empty_is_a_fact",
        "text": "No values found means the table exists and is empty. That is a finding.",
    },
    {
        "id": "two_clocks",
        "text": "RAR empty while VBRK is full is two clocks, not a failed click.",
    },
    {
        "id": "new_path",
        "text": "One miss is a fact. The next move is a different object, never the same key.",
    },
]


def _mem(mem: NavMemory | None = None) -> NavMemory:
    return mem or default_memory()


def say(thought: str, table: str = "", action: str = "", mem: NavMemory | None = None) -> str:
    text = (thought or "").strip()
    if not text:
        return ""
    _mem(mem).add_thought(text, table, action)
    return text


def believe(
    table: str,
    kind: str,
    *,
    entries: int | None = None,
    status: str = "",
    source: str = "glass",
    thought: str = "",
    mem: NavMemory | None = None,
) -> dict[str, Any]:
    """Write a fact. Glass overwrites a prior. A prior does not overwrite glass."""
    db = _mem(mem)
    name = (table or "").strip().upper()
    old = db.get_belief(name)
    if old and (old.get("source") or "") == "glass" and source == "prior":
        return old
    payload = {"entries": entries, "status": (status or "")[:180]}
    db.set_belief(name, kind, payload, thought=thought, source=source)
    if kind == "missing_table":
        note_missing_table(name, status)
    if thought:
        say(thought, name, kind, mem=db)
    return db.get_belief(name) or {"key": name, "kind": kind, **payload}


def belief(table: str, mem: NavMemory | None = None) -> dict[str, Any] | None:
    return _mem(mem).get_belief(table)


def observe(
    table: str,
    *,
    status: str = "",
    blob: str = "",
    entries: int | None = None,
    notes: str = "",
    mem: NavMemory | None = None,
) -> dict[str, Any]:
    """Turn one glass sitting into a belief and a spoken thought."""
    name = (table or "").strip().upper()
    judged = assess_load(status, f"{blob} {notes}", name)
    if judged["kind"] == "missing_table" or judged["kind"] == "leftover":
        thought = (
            f"{name} is not on this dictionary. SAP: {(judged['text'] or status or notes)[:120]}. "
            "I will not Execute. I will not try Online or List Output."
        )
        if judged.get("leftover"):
            thought += f" The field list is still {judged['leftover']}."
        believe(name, "missing_table", status=judged["text"] or status or notes, thought=thought, mem=mem)
        return {"action": "skip", "thought": thought, "kind": "missing_table", "table": name}
    if judged["kind"] == "auth":
        thought = f"{name} is not authorized. That is a finding. I stop this table."
        believe(name, "auth", status=judged["text"], thought=thought, mem=mem)
        return {"action": "skip", "thought": thought, "kind": "auth", "table": name}
    if judged["kind"] == "empty" or entries == 0:
        thought = (
            f"{name} exists and is empty (No values found / F7 = 0). "
            "That is a fact. One Execute is enough to show the blank list. I will not retry."
        )
        believe(name, "empty", entries=0, status=status or "No values found", thought=thought, mem=mem)
        return {"action": "confirm", "thought": thought, "kind": "empty", "table": name}
    if entries is not None:
        thought = f"{name} is LIVE — {entries:,} entries on this book. I will open the list and read rows."
        believe(name, "live", entries=entries, status=status, thought=thought, mem=mem)
        return {"action": "execute", "thought": thought, "kind": "live", "table": name, "entries": entries}
    thought = f"{name} loaded. Status is clean. I will count with F7, then Execute to read contents."
    say(thought, name, "look", mem=mem)
    return {"action": "look", "thought": thought, "kind": "ok", "table": name}


def decide(table: str, *, confirm: bool = False, mem: NavMemory | None = None) -> dict[str, Any]:
    """What a competent person would do next with this table name."""
    name = (table or "").strip().upper()
    rec = belief(name, mem=mem)
    if rec is None:
        thought = (
            f"I do not yet have a glass fact for {name}. "
            "I will type it in SE16N, read the status strip, and only then decide F7/F8."
        )
        say(thought, name, "look", mem=mem)
        return {"action": "look", "thought": thought, "kind": "unknown", "table": name}
    kind = rec.get("kind") or ""
    if kind == "missing_table":
        thought = (
            f"I already know {name} does not exist on this dictionary"
            + (f" ({rec.get('status')})" if rec.get("status") else "")
            + ". I will not type it again to Execute. Next table."
        )
        if confirm:
            thought = (
                f"{name} was named. I will put it on the glass so you can see the red strip, "
                "then I stop. I will not F8."
            )
            say(thought, name, "show_and_stop", mem=mem)
            return {"action": "show_and_stop", "thought": thought, "kind": kind, "table": name}
        say(thought, name, "skip", mem=mem)
        return {"action": "skip", "thought": thought, "kind": kind, "table": name}
    if kind == "auth":
        thought = f"I already know {name} is not authorized. Skipping."
        say(thought, name, "skip", mem=mem)
        return {"action": "skip", "thought": thought, "kind": kind, "table": name}
    if kind == "empty":
        thought = (
            f"{name} exists and is empty. I will not hunt for rows that are not there. "
            "I keep that as the RAR/process fact."
        )
        say(thought, name, "confirm", mem=mem)
        return {"action": "confirm", "thought": thought, "kind": kind, "table": name, "entries": 0}
    n = rec.get("entries")
    thought = (
        f"{name} is LIVE"
        + (f" — {int(n):,} entries" if isinstance(n, int) else "")
        + ". I open the list and read the contents."
    )
    say(thought, name, "execute", mem=mem)
    return {"action": "execute", "thought": thought, "kind": kind, "table": name, "entries": n}


def next_best(process: str = "") -> str:
    """Consultant next step from what we already believe."""
    db = default_memory()
    facts = {b["key"]: b for b in db.all_beliefs()}
    rar_empty = [
        t
        for t in ("FARR_D_CONTRACT", "FARR_D_POB", "FARR_D_DEFITEM")
        if facts.get(t, {}).get("kind") == "empty"
    ]
    rar_miss = facts.get("FARR_D_REVENUE", {}).get("kind") == "missing_table"
    vbrk = facts.get("VBRK", {}).get("entries")
    if rar_miss or rar_empty:
        inv = f"{int(vbrk):,} customer invoices" if isinstance(vbrk, int) else "classic billing"
        return (
            "RAR revenue table is not on this dictionary and the contract table is empty. "
            f"The commercial clock is still {inv}. Two clocks — do not wait for FARR_D_REVENUE."
        )
    if isinstance(facts.get("T001", {}).get("entries"), int):
        return f"Company codes on this book: {facts['T001']['entries']:,}. Design starts there."
    proc = (process or "").strip()
    if proc:
        return f"Next: prove the spine tables for {proc} on the glass, status strip first."
    return "Next: type a table that exists, read the status strip, then count and open it."


def seed_priors(mem: NavMemory | None = None) -> dict[str, int]:
    """Load LIVE_COUNTS and this sitting's proven facts. Glass later overwrites."""
    db = _mem(mem)
    n = 0
    roots = [
        Path("data/runs/analysis_mega/LIVE_COUNTS.json"),
        Path("data/runs/analysis_copc/LIVE_COUNTS.json"),
    ]
    for path in roots:
        if not path.is_file():
            continue
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = (row.get("table") or "").strip().upper()
            n_ent = row.get("entries_found")
            if not name or n_ent is None:
                continue
            kind = "empty" if int(n_ent) == 0 else "live"
            believe(
                name,
                kind,
                entries=int(n_ent),
                status=str(row.get("notes") or "")[:120],
                source="prior",
                mem=db,
            )
            n += 1
    # This sitting: proven on the glass, 2026-08-14.
    believe(
        "FARR_D_REVENUE",
        "missing_table",
        status="FARR_D_REVENUE does not exist; check the name",
        source="glass",
        thought="SAP said FARR_D_REVENUE does not exist. Permanent. Never Execute it.",
        mem=db,
    )
    believe(
        "FARR_D_CONTRACT",
        "empty",
        entries=0,
        status="No values found",
        source="glass",
        thought="FARR_D_CONTRACT exists and is empty on this book.",
        mem=db,
    )
    believe(
        "T001",
        "live",
        entries=1791,
        status="T001: Display of Entries Found",
        source="glass",
        thought="T001 list opened — 1,791 company codes. Uncapped F8 works on a real table.",
        mem=db,
    )
    return {"priors": n, "beliefs": db.stats().get("beliefs") or 0}


def snapshot(mem: NavMemory | None = None) -> dict[str, Any]:
    db = _mem(mem)
    thoughts = db.recent_thoughts(8)
    beliefs = []
    ranked = db.all_beliefs()
    rank = {"missing_table": 0, "auth": 1, "empty": 2, "live": 3}
    ranked.sort(key=lambda b: (0 if (b.get("source") == "glass") else 1, rank.get(b.get("kind") or "", 9), b.get("key") or ""))
    for b in ranked[:16]:
        n = b.get("entries")
        label = b.get("kind") or ""
        if label == "live" and isinstance(n, int):
            label = f"LIVE {n:,}"
        elif label == "empty":
            label = "empty"
        elif label == "missing_table":
            label = "does not exist"
        beliefs.append(
            {
                "table": b.get("key"),
                "kind": b.get("kind"),
                "label": label,
                "status": (b.get("status") or "")[:80],
                "source": b.get("source") or "",
            }
        )
    last = thoughts[0]["thought"] if thoughts else next_best()
    return {
        "thought": last,
        "next": next_best(),
        "lessons": LESSONS,
        "beliefs": beliefs,
        "thoughts": thoughts,
        "memory": db.stats(),
    }
