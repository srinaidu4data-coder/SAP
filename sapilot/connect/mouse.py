"""
Visible mouse control for Co-pilot demos.

SAP GUI Scripting normally sets fields/clicks with zero cursor motion.
This module moves the real Windows cursor so you can *see* the Co-pilot work.
"""

from __future__ import annotations

import logging
import math
import os
import time
from typing import Any

log = logging.getLogger(__name__)


def mouse_enabled() -> bool:
    """Default ON unless SAPILOT_SHOW_MOUSE=0."""
    return os.environ.get("SAPILOT_SHOW_MOUSE", "1").strip() not in {"0", "false", "False", "no"}


def get_cursor() -> tuple[int, int]:
    import win32api  # type: ignore

    return win32api.GetCursorPos()


def set_cursor(x: int, y: int) -> None:
    import win32api  # type: ignore

    win32api.SetCursorPos((int(x), int(y)))


def move_to(
    x: int,
    y: int,
    *,
    duration: float | None = None,
    steps: int | None = None,
) -> None:
    """
    Smoothly move the mouse to (x, y) so motion is visible.
    duration ~0.25–0.6s by default.
    """
    if not mouse_enabled():
        set_cursor(x, y)
        return

    import win32api  # type: ignore

    x0, y0 = win32api.GetCursorPos()
    dist = math.hypot(x - x0, y - y0)
    if duration is None:
        duration = min(0.85, max(0.18, dist / 1800.0))
    if steps is None:
        steps = max(12, int(duration * 90))

    for i in range(1, steps + 1):
        t = i / steps
        # ease-in-out
        e = t * t * (3 - 2 * t)
        xi = int(x0 + (x - x0) * e)
        yi = int(y0 + (y - y0) * e)
        win32api.SetCursorPos((xi, yi))
        time.sleep(duration / steps)
    win32api.SetCursorPos((int(x), int(y)))
    log.debug("mouse → (%s,%s)", x, y)


def click(x: int | None = None, y: int | None = None, *, double: bool = False) -> None:
    """Move (optional) and left-click."""
    import win32api  # type: ignore
    import win32con  # type: ignore

    if x is not None and y is not None:
        move_to(x, y)
        time.sleep(0.05)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.04)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    if double:
        time.sleep(0.08)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.04)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def click_rect(left: int, top: int, width: int, height: int) -> tuple[int, int]:
    """Click center of a rectangle."""
    cx = int(left + max(width, 1) / 2)
    cy = int(top + max(height, 1) / 2)
    click(cx, cy)
    return cx, cy


def sap_component_screen_rect(com_obj: Any) -> tuple[int, int, int, int] | None:
    """
    Best-effort screen rectangle for a SAP GUI Scripting component.
    Returns (left, top, width, height) in screen pixels, or None.
    """
    try:
        # Prefer absolute screen coordinates when exposed
        left = int(getattr(com_obj, "ScreenLeft", None) or getattr(com_obj, "Left", 0))
        top = int(getattr(com_obj, "ScreenTop", None) or getattr(com_obj, "Top", 0))
        # Some builds only have relative Left/Top — try Absolute*
        try:
            left = int(com_obj.ScreenLeft)
            top = int(com_obj.ScreenTop)
        except Exception:
            pass
        width = int(getattr(com_obj, "Width", 80) or 80)
        height = int(getattr(com_obj, "Height", 20) or 20)
        if width <= 0 or height <= 0:
            return None
        # If ScreenLeft missing and Left is tiny, may be relative — still try
        return left, top, width, height
    except Exception as e:
        log.debug("no screen rect: %s", e)
        return None


def click_sap_component(com_obj: Any) -> bool:
    """Move mouse to SAP control and click. Returns True if done visually."""
    if not mouse_enabled():
        return False
    rect = sap_component_screen_rect(com_obj)
    if not rect:
        return False
    left, top, w, h = rect
    # Guard absurd coords
    if left < -100 or top < -100 or left > 8000 or top > 8000:
        return False
    click_rect(left, top, w, h)
    time.sleep(0.08)
    return True


def focus_window(hwnd: int) -> None:
    import win32con  # type: ignore
    import win32gui  # type: ignore

    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)
    except Exception:
        pass


def click_window_point(hwnd: int, rel_x: float, rel_y: float) -> tuple[int, int]:
    """
    Click a relative point inside a window (0..1).
    Used for login fields when COM has no session (scripting off).
    SAP classic logon layout (approx):
      Client ~ (0.42, 0.40), User ~ (0.42, 0.46), Password ~ (0.42, 0.52)
    """
    import win32gui  # type: ignore

    focus_window(hwnd)
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    w, h = right - left, bottom - top
    x = int(left + w * rel_x)
    y = int(top + h * rel_y)
    click(x, y)
    return x, y


def demo_wiggle(hwnd: int | None = None) -> None:
    """Visible proof the mouse driver works — sweeps across SAP window."""
    import win32gui  # type: ignore

    if hwnd is None:
        def find() -> int | None:
            found: list[int] = []

            def cb(h: int, _: Any) -> None:
                if win32gui.IsWindowVisible(h):
                    cls = win32gui.GetClassName(h)
                    title = win32gui.GetWindowText(h)
                    if cls == "SAP_FRONTEND_SESSION" or "SAP Easy Access" in title:
                        found.append(h)

            win32gui.EnumWindows(cb, None)
            return found[0] if found else None

        hwnd = find()
    if not hwnd:
        # just move on desktop
        x, y = get_cursor()
        move_to(x + 200, y - 100)
        move_to(x, y)
        return
    focus_window(hwnd)
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    pts = [
        (left + 80, top + 80),
        (right - 80, top + 80),
        (right - 80, bottom - 80),
        (left + 80, bottom - 80),
        ((left + right) // 2, (top + bottom) // 2),
    ]
    for p in pts:
        move_to(p[0], p[1], duration=0.35)
        time.sleep(0.1)
