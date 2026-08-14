"""Ask a sentence, get a process analysis. The t-code box is not the ask box."""

from sapilot.product.chat import answer, _extract_process


def test_empty_ask_fails():
    assert answer("").get("ok") is False


def test_rar_sentence_is_rar_not_collections():
    q = "Analyze complete RAR process with complete granular level of scenario analysis"
    assert "rar" in _extract_process(q).lower()
    rec = answer(q)
    assert rec["ok"]
    assert rec["source"] == "library"
    assert "Revenue" in (rec.get("title") or "")
    assert "RAI" in rec["text"]
    assert "Point-in-time" in rec["text"]
    assert any(s["tcode"] == "FARR_RAI_MON" for s in rec["steps"])
    assert "collections" not in (rec.get("title") or "").lower()


def test_ifrs_alias():
    rec = answer("explain IFRS 15 revenue")
    assert rec["ok"]
    assert rec["source"] == "library"
    assert "Revenue" in (rec.get("title") or "")
