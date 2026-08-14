"""Instant analysis does not wait on SAP GUI."""

from sapilot.product.fast_analyze import load_live_counts, run_fast


def test_live_counts_include_vbak():
    c = load_live_counts()
    assert c.get("VBAK", {}).get("entries_found") == 12255
    assert c.get("VBRK", {}).get("entries_found") == 5982


def test_rar_fast_report_has_hops_and_document():
    rec = run_fast("Analyze complete RAR process with complete granular level of scenario analysis")
    assert rec["ok"]
    assert rec["status"] == "done"
    blob = " ".join(rec.get("narrative") or []) + " " + " ".join(rec.get("hops") or [])
    assert "12,255" in blob or "12255" in blob.replace(",", "")
    assert rec.get("report_url", "").startswith("/research/")
    assert rec.get("scenarios")
    assert rec.get("studies")
    drill = rec.get("drill") or {}
    assert drill.get("cycles")
    assert drill.get("layers", {}).get("total", 0) >= 100
    assert drill.get("display_walk")
    assert any(c.get("can_walk_e2e") for c in drill["cycles"])
    assert rec.get("excel_url")
    assert rec.get("rules")
    assert any("credit" in (r.get("rule") or "").lower() or "KNKK" in (r.get("evidence") or "") for r in rec["rules"])
