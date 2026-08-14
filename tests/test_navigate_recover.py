"""Navigation classifies errors and decides retry vs give-up. No SAP needed."""

from sapilot.product.navigate import SCREEN_HINTS, classify


def test_se16n_title_matches():
    rec = classify("SAP Easy Access   (APEX-2023)", expect="SE16N")
    assert rec["kind"] == "menu"
    assert rec["expect_ok"] is False
    rec = classify("General Table Display", expect="SE16N")
    assert rec["kind"] == "se16n"
    assert rec["expect_ok"] is True


def test_wrong_tx_is_not_a_successful_se16n_landing():
    rec = classify("Customer Display: Initial Screen", expect="SE16N")
    assert rec["expect_ok"] is False
    rec = classify("Customer Display: Initial Screen", expect="ME23N")
    assert rec["expect_ok"] is False
    rec = classify("Display Purchase Order", expect="ME23N")
    assert rec["expect_ok"] is True


def test_unit_language_error_is_retry_not_missing_table():
    rec = classify(
        "General Table Display",
        status="Unit VBA is not created in language EN",
        blob="View details Save Cancel",
        expect="SE16N",
    )
    assert rec["retry"] is True
    assert rec["error"] == "nav"


def test_table_does_not_exist_is_a_finding():
    rec = classify(
        "General Table Display",
        status="Table FARR_D_REVENUE does not exist",
        expect="SE16N",
    )
    assert rec["retry"] is False
    assert rec["error"] == "finding"


def test_create_screen_detected():
    rec = classify("Create Purchase Order", expect="ME23N")
    assert rec["kind"] == "create"
    assert rec["expect_ok"] is False


def test_blank_shell():
    rec = classify("SAP", expect="VA03")
    assert rec["kind"] == "shell"
    assert rec["expect_ok"] is False


def test_hints_cover_display_hops():
    for code in ("VA03", "VF03", "FB03", "FARR_RAI_MON", "SE16N", "XD03"):
        assert code in SCREEN_HINTS
