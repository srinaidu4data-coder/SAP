"""Any named process returns a display spine. Catalog names are examples."""

from sapilot.product.analyze import analyze_process


def test_empty_name_fails():
    assert analyze_process("").get("ok") is False


def test_unknown_process_still_walkable():
    rec = analyze_process("rebate settlement")
    assert rec["ok"]
    assert rec["source"] == "generic"
    assert rec["steps"]
    assert any(s["tcode"] == "SE16N" for s in rec["steps"])


def test_library_process_not_just_ptp():
    rec = analyze_process("treasury")
    assert rec["ok"]
    assert rec["source"] == "library"
    assert rec["steps"]


def test_rar_is_a_first_class_named_process():
    rec = analyze_process("RAR")
    assert rec["ok"]
    assert rec["source"] == "library"
    assert "AR" not in rec["title"] or "Revenue" in rec["title"]
    assert any(s["tcode"] == "FARR_RAI_MON" for s in rec["steps"])
    assert any(s["tcode"] == "VF03" for s in rec["steps"])
    assert analyze_process("IFRS 15")["source"] == "library"


def test_catalog_example_still_works():
    rec = analyze_process("order to cash")
    assert rec["ok"]
    assert rec["source"] == "catalog-example"
    assert rec["asked"] == "order to cash"
