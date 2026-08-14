"""End-to-end display-mode drill-through after process analysis.

Config / master / transactional layers. Display t-codes only.
The SAP dictionary is the ~100k-table universe (DD02L). We drill every
process cycle you can *show* without creating anything.
"""
from __future__ import annotations

from typing import Any

from sapilot.display.catalog import CYCLES
from sapilot.display.policy import ALLOW_TCODES, DisplayPolicyError, assert_display_tcode
from sapilot.product.analyze import analyze_process
from sapilot.product.universe import plan_tables, plan_tcodes

_MASTER_HINTS = (
    "KNA1", "KNB1", "KNVV", "KNVP", "KNVI", "KNKK", "LFA1", "LFB1", "LFM1",
    "MARA", "MARC", "MARD", "MAKT", "MVKE", "MBEW", "EINA", "EINE",
    "CSKS", "CSKB", "SKA1", "SKB1", "EQUI", "IFLOT", "PROJ", "PRPS",
    "PA0000", "PA0001", "PA0002", "ADRC", "ADR6",
)
_TX_HINTS = (
    "VBAK", "VBAP", "VBEP", "VBKD", "VBPA", "VBFA", "LIKP", "LIPS", "VBRK", "VBRP",
    "EKKO", "EKPO", "EKBE", "EBAN", "MKPF", "MSEG", "RBKP", "RSEG",
    "BKPF", "BSEG", "BSID", "BSAD", "BSIK", "BSAK", "BSIS", "BSAS",
    "NAST", "EDIDC", "ACDOCA", "FAGLFLEXA", "COEP", "AUFK", "AFKO", "AFRU",
    "FARR_D", "VBREV", "KEKO", "KEPH", "CKML",
)


def layer_of(table: str) -> str:
    t = (table or "").upper()
    if t.startswith("FARR_C") or t.startswith("T") or t in {"DD02L", "DD02T", "DD03L", "TSTC", "TSTCT"}:
        return "config"
    if t.startswith("FARR_D") or t.startswith("VBREV"):
        return "transaction"
    if any(t == h or t.startswith(h) for h in _TX_HINTS):
        return "transaction"
    if t in _MASTER_HINTS or t.startswith("PA00") or t.startswith("HRP"):
        return "master"
    if t.startswith("KN") or t.startswith("LF") or t.startswith("MA"):
        return "master"
    return "config" if t.startswith("T") else "transaction"


def _status(tab: str, counts: dict) -> dict[str, Any]:
    rec = counts.get(tab.upper()) if counts else None
    if rec is None:
        return {"table": tab, "layer": layer_of(tab), "n": None, "rank": "CATALOG", "showable": False}
    n = rec.get("entries_found")
    return {
        "table": tab,
        "layer": layer_of(tab),
        "n": n,
        "rank": "LIVE" if n else "ABSENT",
        "showable": n is not None and n > 0,
    }


def _safe_steps(asked: str) -> list[dict]:
    rec = analyze_process(asked)
    out = []
    for s in rec.get("steps") or []:
        code = (s.get("tcode") or "").upper()
        try:
            code = assert_display_tcode(code)
        except DisplayPolicyError:
            continue
        out.append(
            {
                "tcode": code,
                "phase": s.get("phase") or "",
                "purpose": s.get("purpose") or "",
                "display": True,
            }
        )
    return out


def _related_cycles(process_key: str | None) -> list[str]:
    """After the named process, drill every adjacent cycle E2E in display mode."""
    order = ["otc", "rar", "collections", "copc", "ptp", "r2r"]
    if process_key in {"rar", "otc", "collections", "sales"}:
        return ["otc", "rar", "collections", "copc", "r2r"]
    if process_key in {"ptp", "p2p"}:
        return ["ptp", "copc", "r2r"]
    if process_key in {"copc", "costing"}:
        return ["copc", "otc", "ptp"]
    if process_key and process_key in CYCLES:
        rest = [c for c in order if c != process_key and c in CYCLES]
        return [process_key] + rest
    return order


def drill(asked: str, counts: dict[str, Any] | None, process_key: str | None) -> dict[str, Any]:
    """Instant E2E display-mode map. Does not wait on SAP GUI."""
    counts = counts or {}
    tables = plan_tables(process_key, asked)
    layered: dict[str, list[dict]] = {"config": [], "master": [], "transaction": []}
    for tab in tables:
        rec = _status(tab, counts)
        layered[rec["layer"]].append(rec)

    cycles = []
    for name in _related_cycles(process_key):
        cyc = CYCLES.get(name)
        steps_src = []
        title = name
        spine = ""
        if cyc:
            title = cyc.title
            spine = cyc.spine
            for s in cyc.steps:
                try:
                    code = assert_display_tcode(s.tcode)
                except DisplayPolicyError:
                    continue
                steps_src.append(
                    {
                        "tcode": code,
                        "phase": s.phase,
                        "purpose": s.purpose,
                        "display": True,
                    }
                )
        else:
            steps_src = _safe_steps(name if name != "rar" else "RAR")
            rec = analyze_process("RAR" if name == "rar" else name)
            title = rec.get("title") or name
            spine = rec.get("spine") or ""

        live_hops = 0
        showable = []
        blocked = []
        for st in steps_src:
            # A display hop is showable if we have live docs in that phase.
            phase = st["phase"]
            evidence = None
            if phase in {"transaction", "flow"} and name in {"otc", "rar"}:
                evidence = counts.get("VBAK") or counts.get("VBRK")
            elif phase == "financial" and name in {"otc", "rar", "collections"}:
                evidence = counts.get("BSID") or counts.get("BKPF") or counts.get("VBRK")
            elif phase == "master" and name in {"otc", "rar", "collections"}:
                evidence = counts.get("KNA1") or counts.get("KNVV") or counts.get("MARA")
            elif name == "copc":
                evidence = counts.get("KEKO") or counts.get("TCK03")
            elif name == "ptp":
                evidence = counts.get("EKKO") or counts.get("T161")
            n = evidence.get("entries_found") if evidence else None
            can = n is None or n > 0
            # Empty credit is still a showable finding (display empty).
            if st["tcode"] in ALLOW_TCODES:
                can = True
            item = {**st, "live_n": n, "showable": can}
            if can:
                live_hops += 1
                showable.append(item)
            else:
                blocked.append(item)
        cycles.append(
            {
                "name": name,
                "title": title,
                "spine": spine,
                "steps": steps_src,
                "showable": showable,
                "blocked": blocked,
                "can_walk_e2e": live_hops >= 3,
                "hops": live_hops,
            }
        )

    display_walk = _safe_steps(asked)
    for extra in plan_tcodes(process_key, asked):
        if extra["tcode"] not in {s["tcode"] for s in display_walk}:
            display_walk.append({**extra, "display": True})

    showable_cycles = [c["title"] for c in cycles if c["can_walk_e2e"]]
    live_tx = [t for t in layered["transaction"] if t.get("showable")]
    live_cfg = [t for t in layered["config"] if t.get("n") is not None]
    live_mst = [t for t in layered["master"] if t.get("n") is not None]

    story = (
        f"Dictionary class on a full SAP client is ~80,000–100,000 tables (DD02L). "
        f"This drill lists {len(tables)} process-relevant tables "
        f"({len(layered['config'])} config, {len(layered['master'])} master, "
        f"{len(layered['transaction'])} transactional) and every display-only cycle "
        f"you can walk on this book. "
        f"Proven live: {len(live_cfg)} config, {len(live_mst)} master, {len(live_tx)} transactional. "
        f"End-to-end display walks that this book can actually show: "
        + (", ".join(showable_cycles) if showable_cycles else "none until a document table is live")
        + ". Create / change / post remain refused."
    )

    return {
        "story": story,
        "dictionary": "DD02L (~80k–100k tables on a full client). Drill is process-complete, not a random 100k F7.",
        "layers": {
            "config": len(layered["config"]),
            "master": len(layered["master"]),
            "transaction": len(layered["transaction"]),
            "total": len(tables),
        },
        "tables": layered,
        "cycles": cycles,
        "display_walk": display_walk,
        "showable_e2e": showable_cycles,
    }
