"""The mind remembers glass facts and refuses to Execute a rejected table."""

from sapilot.learn.memory import NavMemory
from sapilot.learn.mind import believe, decide, observe, snapshot
from sapilot.learn.policy import suggest


def test_missing_table_is_skip_next_time(tmp_path):
    mem = NavMemory(tmp_path / "nav.db")
    rec = observe(
        "FARR_D_REVENUE",
        status="FARR_D_REVENUE does not exist; check the name",
        blob="Data base: FARR_D_REVENUE Company Codes BUTXT ORT01 LAND1",
        mem=mem,
    )
    assert rec["action"] == "skip"
    assert rec["kind"] == "missing_table"
    nxt = decide("FARR_D_REVENUE", mem=mem)
    assert nxt["action"] == "skip"
    assert "not exist" in nxt["thought"].lower() or "will not" in nxt["thought"].lower()


def test_named_missing_table_is_show_and_stop_not_f8(tmp_path):
    mem = NavMemory(tmp_path / "nav.db")
    believe(
        "FARR_D_REVENUE",
        "missing_table",
        status="does not exist; check the name",
        source="glass",
        mem=mem,
    )
    nxt = decide("FARR_D_REVENUE", confirm=True, mem=mem)
    assert nxt["action"] == "show_and_stop"
    assert "F8" in nxt["thought"] or "stop" in nxt["thought"].lower()


def test_empty_table_is_a_fact_not_a_retry(tmp_path):
    mem = NavMemory(tmp_path / "nav.db")
    rec = observe("FARR_D_CONTRACT", status="No values found", entries=0, mem=mem)
    assert rec["kind"] == "empty"
    nxt = decide("FARR_D_CONTRACT", mem=mem)
    assert nxt["action"] == "confirm"
    assert nxt.get("entries") == 0


def test_suggest_stops_on_status_error_instead_of_f8():
    act = suggest(
        "General Table Display",
        "FARR_D_REVENUE does not exist; check the name",
        "Data base: FARR_D_REVENUE",
        "open_list",
    )
    assert act is not None
    assert act.get("kind") == "stop"


def test_snapshot_speaks_lessons(tmp_path):
    mem = NavMemory(tmp_path / "nav.db")
    believe("T001", "live", entries=1791, source="glass", thought="T001 is LIVE.", mem=mem)
    snap = snapshot(mem)
    assert snap["thought"]
    assert any(x["id"] == "no_f8_missing" for x in snap["lessons"])
    tables = [b["table"] for b in snap["beliefs"]]
    assert "T001" in tables
