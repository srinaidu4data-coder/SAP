"""Recursive GUI object-tree → ScreenSnapshot JSON (text-tree first, pixels last)."""

from __future__ import annotations

import logging
from typing import Any

from sapilot.schemas import GuiElement, ScreenSnapshot, utcnow

log = logging.getLogger(__name__)

# COM type number → friendly name (subset)
GUI_TYPE_NAMES = {
    0: "GuiComponent",
    1: "GuiSession",
    2: "GuiApplication",
    10: "GuiFrameWindow",
    11: "GuiMainWindow",
    12: "GuiModalWindow",
    21: "GuiLabel",
    30: "GuiTextField",
    31: "GuiCTextField",
    32: "GuiPasswordField",
    33: "GuiComboBox",
    34: "GuiOkCodeField",
    40: "GuiButton",
    41: "GuiRadioButton",
    42: "GuiCheckBox",
    50: "GuiTabStrip",
    51: "GuiTab",
    62: "GuiTableControl",
    80: "GuiShell",
    100: "GuiStatusbar",
    103: "GuiToolbar",
    121: "GuiMenubar",
    122: "GuiMenu",
    127: "GuiTitlebar",
    171: "GuiContainerShell",
}


def _safe_str(obj: Any, attr: str, default: str = "") -> str:
    try:
        v = getattr(obj, attr, default)
        return "" if v is None else str(v)
    except Exception:
        return default


def _safe_bool(obj: Any, attr: str, default: bool = False) -> bool:
    try:
        return bool(getattr(obj, attr, default))
    except Exception:
        return default


def serialize_element(com_obj: Any, depth: int = 0, max_depth: int = 12) -> GuiElement:
    """Serialize a COM GuiComponent to GuiElement (no screenshots)."""
    eid = _safe_str(com_obj, "Id")
    typ_num = None
    try:
        typ_num = int(com_obj.TypeAsNumber)
    except Exception:
        try:
            typ_num = int(getattr(com_obj, "Type", 0) or 0)
        except Exception:
            typ_num = 0
    type_name = GUI_TYPE_NAMES.get(typ_num or 0, f"Type{typ_num}")

    children: list[GuiElement] = []
    if depth < max_depth:
        try:
            count = int(com_obj.Children.Count)
            for i in range(count):
                try:
                    child = com_obj.Children(i)
                    children.append(serialize_element(child, depth + 1, max_depth))
                except Exception as e:
                    log.debug("Skip child %s: %s", i, e)
        except Exception:
            pass

    extra: dict[str, Any] = {}
    try:
        if hasattr(com_obj, "CharHeight"):
            extra["char_height"] = com_obj.CharHeight
    except Exception:
        pass

    return GuiElement(
        id=eid,
        type=type_name,
        name=_safe_str(com_obj, "Name"),
        text=_safe_str(com_obj, "Text"),
        changeable=_safe_bool(com_obj, "Changeable"),
        highlighted=_safe_bool(com_obj, "Highlighted"),
        tooltip=_safe_str(com_obj, "Tooltip"),
        children=children,
        extra=extra,
    )


def serialize_session(session: Any) -> ScreenSnapshot:
    """Full screen snapshot from a live GuiSession COM object."""
    wnd = session.FindById("wnd[0]")
    elements = serialize_element(wnd)
    status = ""
    try:
        status = str(session.FindById("wnd[0]/sbar").Text)
    except Exception:
        pass

    tcode = ""
    program = ""
    screen_number = ""
    try:
        info = session.Info
        tcode = _safe_str(info, "Transaction")
        program = _safe_str(info, "Program")
        screen_number = _safe_str(info, "ScreenNumber")
    except Exception:
        pass

    title = _safe_str(wnd, "Text")
    return ScreenSnapshot(
        tcode=tcode,
        program=program,
        screen_number=str(screen_number),
        title=title,
        status_bar=status,
        elements=elements,
        captured_at=utcnow(),
    )


def flatten_elements(root: GuiElement) -> list[dict[str, str]]:
    """Flat list for planner context (ids + text + type)."""
    out: list[dict[str, str]] = []

    def walk(el: GuiElement) -> None:
        out.append(
            {
                "id": el.id,
                "type": el.type,
                "name": el.name,
                "text": el.text[:200] if el.text else "",
                "changeable": str(el.changeable),
            }
        )
        for c in el.children:
            walk(c)

    walk(root)
    return out
