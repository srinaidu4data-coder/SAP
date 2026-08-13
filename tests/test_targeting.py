from __future__ import annotations

import types

import pytest

from sapilot.autobot.targeting import (
    TargetMatch,
    locate_element,
    locate_via_ocr,
    locate_via_scripting,
    locate_via_uia,
)


class _FakeElement:
    def __init__(self, left, top, width, height):
        self.ScreenLeft = left
        self.ScreenTop = top
        self.Width = width
        self.Height = height


class _FakeSession:
    def __init__(self, controls: dict[str, _FakeElement]):
        self._controls = controls

    def FindById(self, control_id: str):
        if control_id not in self._controls:
            raise Exception(f"not found: {control_id}")
        return self._controls[control_id]


def test_scripting_tier_exact_hit():
    session = _FakeSession({"wnd[0]/usr/ctxtRF02K-LIFNR": _FakeElement(100, 200, 40, 20)})
    hit = locate_via_scripting(session, "wnd[0]/usr/ctxtRF02K-LIFNR")
    assert hit is not None
    assert hit.tier == "scripting"
    assert hit.confidence == 1.0
    assert hit.x == 120 and hit.y == 210  # center of the box


def test_scripting_tier_miss_returns_none():
    session = _FakeSession({})
    assert locate_via_scripting(session, "wnd[0]/usr/does_not_exist") is None


def test_uia_tier_bogus_hwnd_returns_none_not_raise():
    # No live window at this handle — must degrade to None, never raise into
    # the caller's automation loop.
    assert locate_via_uia(999_999_999, "Vendor Number") is None


def test_ocr_tier_missing_tesseract_binary_returns_none_not_raise():
    # This environment has pytesseract installed but not the Tesseract-OCR
    # binary — must degrade gracefully, not crash the whole pipeline.
    assert locate_via_ocr("nonexistent_screenshot.png", "Vendor Number") is None


def test_ocr_tier_parses_word_boxes_and_matches(monkeypatch):
    """Mock pytesseract's image_to_data output shape to verify the box
    parsing / center computation / fuzzy match without needing the real
    Tesseract binary installed."""
    import pytesseract

    fake_data = {
        "text": ["", "Vendor", "Number", "Company", "Code"],
        "conf": ["-1", "92", "88", "90", "85"],
        "left": [0, 20, 90, 220, 300],
        "top": [0, 30, 30, 30, 30],
        "width": [0, 60, 55, 70, 40],
        "height": [0, 20, 20, 20, 20],
    }
    monkeypatch.setattr(pytesseract, "image_to_data", lambda img, output_type=None: fake_data)

    fake_image_module = types.SimpleNamespace(open=lambda p: types.SimpleNamespace(crop=lambda box: None))
    monkeypatch.setitem(__import__("sys").modules, "PIL.Image", fake_image_module)
    import PIL

    monkeypatch.setattr(PIL, "Image", fake_image_module, raising=False)

    result = locate_via_ocr("fake_path.png", "Vendor Number")
    assert result is not None
    assert result.tier == "ocr"
    assert result.x == 50 and result.y == 40  # center of the "Vendor" box
    assert result.confidence >= 0.6


def test_orchestrator_falls_through_all_tiers_to_none():
    """When scripting, UIA, and OCR all miss, locate_element must return
    None cleanly so the caller knows to fall back to full VLM vision —
    never raise."""

    class FailingSession:
        def FindById(self, cid):
            raise Exception("not found")

    result = locate_element(
        session=FailingSession(),
        control_id="wnd[0]/usr/nope",
        hwnd=999_999_999,
        screenshot_path="nonexistent.png",
        target_text="Vendor Number",
    )
    assert result is None


def test_orchestrator_prefers_scripting_over_lower_tiers():
    session = _FakeSession({"wnd[0]/usr/ctxtRF02K-LIFNR": _FakeElement(0, 0, 10, 10)})
    result = locate_element(
        session=session,
        control_id="wnd[0]/usr/ctxtRF02K-LIFNR",
        hwnd=999_999_999,  # would miss if UIA were tried
        screenshot_path=None,
        target_text="Vendor Number",
    )
    assert result is not None
    assert result.tier == "scripting"
