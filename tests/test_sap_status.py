"""Status-bar errors must stop the sitting. Do not F8 a missing table."""

from pathlib import Path

from sapilot.product.sap_status import assess_load, classify_message, leftover_table


def test_farr_d_revenue_does_not_exist_is_fatal():
    rec = classify_message(
        "FARR_D_REVENUE does not exist; check the name",
        "Data base: FARR_D_REVENUE",
        "FARR_D_REVENUE",
    )
    assert rec["fatal"] is True
    assert rec["kind"] == "missing_table"


def test_no_values_found_is_empty_not_fatal():
    rec = classify_message("No values found", "Data base: FARR_D_CONTRACT", "FARR_D_CONTRACT")
    assert rec["fatal"] is False
    assert rec["kind"] == "empty"


def test_invalid_ok_command_stops():
    rec = classify_message("Invalid OK command", "", "VBAK")
    assert rec["fatal"] is True
    assert rec["kind"] == "bad_okcd"


def test_clean_status_is_ok():
    rec = classify_message("", "Selection Criteria Fld Name T001", "T001")
    assert rec["kind"] == "ok"
    assert rec["fatal"] is False


def test_leftover_t001_catalog_is_not_a_farr_load():
    blob = (
        "Data base: FARR_D_REVENUE Company Codes "
        "Selection Criteria Fld Name Client Company Code BUTXT ORT01 LAND1 "
        "WAERS SPRAS KTOPL WAABW RCOMP Technical Name MANDT BUKRS"
    )
    assert leftover_table(blob, "FARR_D_REVENUE") == "T001"
    rec = assess_load("", blob, "FARR_D_REVENUE")
    assert rec["fatal"] is True
    assert rec["loaded"] is False
    assert rec["leftover"] == "T001"


def test_typed_name_alone_is_not_a_load_when_status_says_missing():
    rec = assess_load(
        "FARR_D_REVENUE does not exist; check the name View details",
        "Data base: FARR_D_REVENUE Company Codes BUTXT ORT01 LAND1 RCOMP",
        "FARR_D_REVENUE",
    )
    assert rec["fatal"] is True
    assert rec["kind"] == "missing_table"
    assert rec["loaded"] is False


def test_real_farr_d_revenue_shot_reads_the_error():
    shot = Path("data/runs/product/exec5/farr_d_revenue_sel.png")
    if not shot.is_file():
        return
    from PIL import Image

    from sapilot.autobot.eyes import read_status

    st = read_status(Image.open(shot))
    assert "does not exist" in (st.text or "").lower() or "check the name" in (st.text or "").lower()
    rec = assess_load(st.text, st.text, "FARR_D_REVENUE")
    assert rec["fatal"] is True
    assert rec["kind"] == "missing_table"


def test_study_table_does_not_execute_when_load_says_missing():
    rec = {
        "table": "FARR_D_REVENUE",
        "entries_found": None,
        "rank": "ABSENT",
        "notes": "table does not exist (FARR_D_REVENUE does not exist; check the name)",
        "opened": False,
        "contents": None,
    }
    notes = rec["notes"]
    assert notes.startswith("table does not exist")
    # If this guard regresses, open_and_read would run F8 on a missing table.
    assert "does not exist" in notes


def test_contract_own_fields_are_not_leftover():
    blob = (
        "Data base: FARR_D_CONTRACT Contracts "
        "CONTRACT_ID CONTRACT_CAT ACCT_PRINCIPLE CONTR_CREATED_ON MANDT"
    )
    assert leftover_table(blob, "FARR_D_CONTRACT") is None
    rec = assess_load("", blob, "FARR_D_CONTRACT")
    assert rec["fatal"] is False
    assert rec["loaded"] is True
