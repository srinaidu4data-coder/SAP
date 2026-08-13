"""Vision-only operator: geometry, status parse, prove protocol. No SAP needed."""

from __future__ import annotations

from sapilot.autobot.eyes import (
    ScreenView,
    WordBox,
    click_point_for_label,
    find_label,
    parse_hit_count,
    parse_status_bar,
    proof_from_view,
    words_contain,
)
from sapilot.autobot.hands import Jacobian, abs_from_frac, servo_to
from sapilot.autobot.operator import HumanEyesHands
from sapilot.autobot.playbooks_human import DEFAULT_PO


def _w(text: str, x: int, y: int, w: int = 40, h: int = 12) -> WordBox:
    return WordBox(text=text, x=x, y=y, w=w, h=h, conf=80, img_w=1000, img_h=800)


def test_parse_status_created_hint_is_not_proof():
    st = parse_status_bar("S  Standard PO created under the number 4500002262")
    assert st.kind == "S"
    assert st.docno == "4500002262"


def test_parse_status_no_values_is_error():
    st = parse_status_bar("No values found")
    assert st.kind == "E"
    assert st.docno is None


def test_find_label_joins_purch_org():
    words = [_w("Purch.", 80, 200), _w("Org.", 130, 200), _w("1710", 220, 200)]
    hit = find_label(words, ["Purch. Org", "Purchasing Organization"])
    assert hit is not None
    assert "Purch" in hit.text


def test_click_right_of_label():
    lab = _w("Supplier", 100, 120, w=70)
    rx, ry = click_point_for_label(lab, side="right")
    assert rx > lab.rx
    assert abs(ry - lab.ry) < 0.02


def test_click_left_of_label_is_checkbox():
    lab = _w("GR-Based IV", 400, 500, w=90)
    rx, ry = click_point_for_label(lab, side="left")
    assert rx < lab.rx
    assert abs(ry - lab.ry) < 0.02


def test_find_label_skips_status_strip():
    words = [
        _w("Purchase", 40, 760, w=80),  # status / chrome if ry>0.93
        _w("Purchasing", 80, 240, w=90),
        _w("Doc", 180, 240, w=40),
    ]
    words[0] = WordBox(
        text="Purchase", x=40, y=760, w=80, h=12, conf=80, img_w=1000, img_h=800
    )
    hit = find_label(words, ["Purchasing Doc"])
    assert hit is not None
    assert "Purchasing" in hit.text


def test_words_contain():
    words = [_w("USSU-VSF01", 200, 120)]
    assert words_contain(words, "USSU-VSF01")
    assert not words_contain(words, "4500002262")


def test_jacobian_learns_from_probe():
    j = Jacobian()
    j.update(10, 0, 20, 0, lr=0.5)
    mx, _ = j.apply(10, 0)
    assert mx > 10


def test_abs_from_frac():
    x, y = abs_from_frac((100, 50, 500, 450), 0.25, 0.5)
    assert x == 200
    assert y == 250


def test_servo_converges_when_cursor_is_target(monkeypatch):
    pos = {"xy": (40, 40)}

    def fake_get():
        return pos["xy"]

    def fake_set(x, y):
        pos["xy"] = (int(x), int(y))

    monkeypatch.setattr("sapilot.autobot.hands.get_cursor", fake_get)
    monkeypatch.setattr("sapilot.autobot.hands.set_cursor", fake_set)
    res = servo_to(40, 40, max_loops=3)
    assert res.ok
    assert res.reason == "on_target"


def test_capabilities_never_scripting():
    op = HumanEyesHands(shot_dir="data/runs/_unit")
    cap = op.capabilities()
    assert cap["scripting"] is False
    assert cap["claim_without_table"] is False
    assert cap["prove_in_se16n"] is True


def test_default_po_keys_are_the_known_ones():
    assert DEFAULT_PO["vendor"] == "USSU-VSF01"
    assert DEFAULT_PO["ekorg"] == "1710"
    assert DEFAULT_PO["knttp"] == "K"


def test_held_status_extracts_docno():
    st = parse_status_bar("Standard PO held under the number 3200000039")
    assert st.docno == "3200000039"


def test_parse_hit_count():
    words = [_w("Number", 40, 80), _w("of", 90, 80), _w("Hits", 120, 80), _w("1", 200, 80)]
    # image 1000x800 so y=80 is mid-header
    assert parse_hit_count(words) == 1


def _view(words: list[WordBox], status: str = "") -> ScreenView:
    from sapilot.autobot.eyes import parse_status_bar as _ps

    return ScreenView(path="", width=1000, height=800, words=words, status=_ps(status))


def test_prove_rejects_unfiltered_500_dump():
    words = [
        _w("Hits", 120, 80),
        _w("500", 200, 80),
        _w("3200000039", 80, 90),  # leftover in the filter field
        _w("4500000002", 80, 400),
    ]
    ok, detail = proof_from_view(_view(words), "3200000039")
    assert ok is False
    assert "500" in detail


def test_prove_rejects_document_display_without_hit_count():
    words = [
        _w("Held", 200, 80),
        _w("Standard", 280, 80),
        _w("PO", 360, 80),
        _w("3200000039", 400, 80),
        _w("Supplier", 200, 160),
    ]
    ok, detail = proof_from_view(_view(words), "3200000039")
    assert ok is False
    assert "hits=" in detail


def test_prove_accepts_one_hit():
    words = [
        _w("Hits", 120, 80),
        _w("1", 200, 80),
        _w("3200000039", 80, 400),
        _w("USSU-VSF01", 400, 400),
    ]
    ok, detail = proof_from_view(_view(words), "3200000039")
    assert ok is True
    assert "1 hit" in detail


def test_title_kind():
    assert HumanEyesHands._title_kind("SAP Easy Access   (APEX-2023)") == "menu"
    assert HumanEyesHands._title_kind("SAP") == "shell"
    assert HumanEyesHands._title_kind("Create Purchase Order") == "tx"
