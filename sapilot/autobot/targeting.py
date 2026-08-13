"""
Tiered element targeting for SAP GUI automation.

Research finding (independently confirmed across desktop-agent benchmarks —
WindowsAgentArena, UFO2, EntWorld — and every major commercial RPA vendor's
documented architecture): pure-vision targeting is the least reliable and
most expensive tier available, and should be the *last* resort, not the
first. The consistent winning pattern is a fallback chain from the most
structured/exact source down to raw pixels:

    1. SAP GUI Scripting (COM control tree)  — exact, near-zero cost.
       Requires sapgui/user_scripting=TRUE; not always available.
    2. Windows UI Automation (UIA)           — structured, but SAP's
       custom-rendered controls often expose thin/inconsistent UIA data.
    3. OCR text-label matching               — cheap, no GPU, works for
       anything with a visible text label (menu items, buttons, field
       labels); blind to icon-only controls.
    4. Full VLM vision (outside this module)  — the existing agent-reads-
       screenshot path in vision_operator.py. Slowest, least precise,
       used only when tiers 1-3 all miss.

Every tier here is optional at runtime: comtypes/uiautomation and the
Tesseract-OCR binary may not be installed, and a SAP session may not be
scriptable. Each locate_via_* function degrades to `None` on any failure
so the orchestrator always falls through cleanly to the next tier instead
of raising into the caller's automation loop.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sapilot.autobot.text_match import best_match

log = logging.getLogger(__name__)


@dataclass
class TargetMatch:
    x: int
    y: int
    tier: str
    confidence: float
    source: str  # human-readable: control id, UIA AutomationId, OCR text, ...


# -- Tier 1: SAP GUI Scripting -----------------------------------------------


def locate_via_scripting(session, control_id: str) -> TargetMatch | None:
    """Exact match via SAP's own COM control tree. Ground truth when available."""
    try:
        el = session.FindById(control_id)
        left, top = int(el.ScreenLeft), int(el.ScreenTop)
        width, height = int(el.Width), int(el.Height)
        cx, cy = left + width // 2, top + height // 2
        return TargetMatch(x=cx, y=cy, tier="scripting", confidence=1.0, source=control_id)
    except Exception as e:
        log.debug("scripting tier miss for %r: %s", control_id, e)
        return None


# -- Tier 2: Windows UI Automation -------------------------------------------


def locate_via_uia(
    hwnd: int,
    target_text: str,
    *,
    max_depth: int = 12,
    min_score: float = 0.6,
) -> TargetMatch | None:
    """
    Best-effort structured fallback when SAP GUI Scripting is unavailable.
    SAP's own controls are frequently thin/invisible to UIA (custom-drawn
    grids, tree controls), so this tier is expected to miss often — that's
    fine, it's a fallback, not a replacement for tier 1.
    """
    try:
        import uiautomation as auto  # type: ignore
    except ImportError:
        log.debug("uia tier unavailable: `pip install comtypes uiautomation`")
        return None

    try:
        root = auto.ControlFromHandle(hwnd)
    except Exception as e:
        log.debug("uia tier: could not bind to hwnd=%s: %s", hwnd, e)
        return None

    candidates: list[tuple[str, tuple[int, int]]] = []

    def walk(control, depth: int = 0) -> None:
        if control is None or depth > max_depth:
            return
        try:
            name = str(getattr(control, "Name", "") or "")
            rect = control.BoundingRectangle
            if name and rect and rect.width() > 0 and rect.height() > 0:
                cx = rect.left + rect.width() // 2
                cy = rect.top + rect.height() // 2
                candidates.append((name, (cx, cy)))
        except Exception:
            pass
        try:
            for child in control.GetChildren():
                walk(child, depth + 1)
        except Exception:
            pass

    try:
        walk(root)
    except Exception as e:
        log.debug("uia tier: tree walk failed: %s", e)
        return None

    if not candidates:
        return None

    match = best_match(target_text, candidates, min_score=min_score)
    if match is None:
        return None
    (cx, cy), score = match
    return TargetMatch(x=cx, y=cy, tier="uia", confidence=score, source=target_text)


# -- Tier 3: OCR text-label matching -----------------------------------------


def locate_via_ocr(
    screenshot_path: str,
    target_text: str,
    *,
    region: tuple[int, int, int, int] | None = None,
    min_score: float = 0.6,
) -> TargetMatch | None:
    """
    OCR every word box in the screenshot (or a sub-region), fuzzy-match
    against target_text. Cheap relative to a full VLM call; blind to
    icon-only controls with no visible text.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        log.debug("ocr tier unavailable: `pip install pytesseract pillow`")
        return None

    try:
        img = Image.open(screenshot_path)
        offset_x, offset_y = 0, 0
        if region:
            left, top, right, bottom = region
            img = img.crop((left, top, right, bottom))
            offset_x, offset_y = left, top
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError:
        log.debug("ocr tier unavailable: Tesseract-OCR binary not found on PATH")
        return None
    except Exception as e:
        log.debug("ocr tier failed: %s", e)
        return None

    candidates: list[tuple[str, tuple[int, int]]] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        conf = data.get("conf", ["-1"] * n)[i]
        try:
            if float(conf) < 0:
                continue
        except (TypeError, ValueError):
            pass
        left, top = int(data["left"][i]), int(data["top"][i])
        w, h = int(data["width"][i]), int(data["height"][i])
        cx = offset_x + left + w // 2
        cy = offset_y + top + h // 2
        candidates.append((text, (cx, cy)))

    if not candidates:
        return None

    match = best_match(target_text, candidates, min_score=min_score)
    if match is None:
        return None
    (cx, cy), score = match
    return TargetMatch(x=cx, y=cy, tier="ocr", confidence=score, source=target_text)


# -- Orchestrator -------------------------------------------------------------


def locate_element(
    *,
    session=None,
    control_id: str | None = None,
    hwnd: int | None = None,
    screenshot_path: str | None = None,
    target_text: str | None = None,
    region: tuple[int, int, int, int] | None = None,
) -> TargetMatch | None:
    """
    Try tiers 1-3 in order, return the first hit. `None` means all
    structured/cheap tiers missed — the caller should fall back to full
    VLM vision (outside this module) as tier 4.
    """
    if session is not None and control_id:
        hit = locate_via_scripting(session, control_id)
        if hit is not None:
            return hit

    if hwnd is not None and target_text:
        hit = locate_via_uia(hwnd, target_text)
        if hit is not None:
            return hit

    if screenshot_path and target_text:
        hit = locate_via_ocr(screenshot_path, target_text, region=region)
        if hit is not None:
            return hit

    return None
