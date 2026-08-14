"""Research plan is large and process-first. No SAP required."""

from sapilot.product.census import parse_entries
from sapilot.product.research import _reason
from sapilot.product.universe import plan_research, plan_tables


def test_rar_plan_is_not_a_dozen_tables():
    rec = plan_research("Analyze complete RAR process with complete granular level of scenario analysis")
    assert rec["ok"]
    assert rec["universe"] >= 150
    assert rec["tables"][0].startswith("FARR") or rec["tables"][0] in {"VBREVK", "VBAK"}
    assert "FARR_D_CONTRACT" in rec["tables"]
    assert "VBRK" in rec["tables"]
    assert rec["tcodes"]
    assert any(s["tcode"] == "SE16N" for s in rec["tcodes"])


def test_unknown_process_still_large():
    rec = plan_research("rebate settlement")
    assert rec["universe"] >= 100
    assert "SE16N" in [s["tcode"] for s in rec["tcodes"]]


def test_parse_entries():
    assert parse_entries("Number of Entries found: 12,255") == 12255
    assert parse_entries("Entries found: 0") == 0
    assert parse_entries("hello") is None


def test_reason_uses_live_counts_only():
    job = {
        "asked": "RAR",
        "title": "Revenue Accounting and Reporting (your process)",
        "counts": [
            {"table": "VBAK", "entries_found": 12255},
            {"table": "LIKP", "entries_found": 7959},
            {"table": "VBRK", "entries_found": 5982},
            {"table": "FARR_D_CONTRACT", "entries_found": 0},
        ],
    }
    _reason(job)
    blob = " ".join(job["narrative"] + job["hops"])
    assert "5,982" in blob or "5982" in blob.replace(",", "")
    assert "FARR" in blob or "RAR" in blob
    assert any(s.get("status") == "LIVE" for s in job["scenarios"])


def test_plan_tables_prioritises_process():
    tabs = plan_tables("rar", "RAR")
    assert tabs.index("FARR_D_CONTRACT") < tabs.index("EKKO")
