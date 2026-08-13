"""
Hands — closed-loop mouse + scoped keys. No SAP GUI Scripting.

A human does not fire one guessed pixel and type. They move, look, correct,
and only type when the field is focused. Visual servoing + online Jacobian
(Piepmeier-style) absorbs DPI and window chrome.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from sapilot.connect.mouse import get_cursor, set_cursor

log = logging.getLogger(__name__)


@dataclass
class Jacobian:
    """2x2 map: mouse delta → observed cursor delta. Identity is a good prior."""

    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0

    def apply(self, dx: float, dy: float) -> tuple[float, float]:
        return self.a * dx + self.b * dy, self.c * dx + self.d * dy

    def update(self, cmd_dx: float, cmd_dy: float, see_dx: float, see_dy: float, *, lr: float = 0.25) -> None:
        """One RLS-lite step from a probe move."""
        if abs(cmd_dx) + abs(cmd_dy) < 1:
            return
        pred_x, pred_y = self.apply(cmd_dx, cmd_dy)
        ex, ey = see_dx - pred_x, see_dy - pred_y
        n = cmd_dx * cmd_dx + cmd_dy * cmd_dy
        self.a += lr * ex * cmd_dx / n
        self.b += lr * ex * cmd_dy / n
        self.c += lr * ey * cmd_dx / n
        self.d += lr * ey * cmd_dy / n


@dataclass
class ClickResult:
    ok: bool
    x: int
    y: int
    loops: int
    reason: str = ""
    journal: list[dict] = field(default_factory=list)


def _click_now(double: bool = False) -> None:
    import win32api  # type: ignore
    import win32con  # type: ignore

    for i in range(2 if double else 1):
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.03)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        if double and i == 0:
            time.sleep(0.06)
    time.sleep(0.08)


def servo_to(
    x: int,
    y: int,
    *,
    jac: Jacobian | None = None,
    tol: int = 5,
    max_loops: int = 8,
    gain: float = 0.65,
) -> ClickResult:
    """Drive the cursor to (x, y) in screen pixels. Closed loop on GetCursorPos."""
    j = jac or Jacobian()
    journal: list[dict] = []
    for n in range(1, max_loops + 1):
        cx, cy = get_cursor()
        ex, ey = x - cx, y - cy
        journal.append({"n": n, "cx": cx, "cy": cy, "ex": ex, "ey": ey})
        if abs(ex) <= tol and abs(ey) <= tol:
            return ClickResult(True, cx, cy, n, "on_target", journal)
        mx, my = j.apply(ex, ey)
        nx = int(cx + mx * gain)
        ny = int(cy + my * gain)
        set_cursor(nx, ny)
        time.sleep(0.04)
        sx, sy = get_cursor()
        j.update(nx - cx, ny - cy, sx - cx, sy - cy)
    cx, cy = get_cursor()
    ok = abs(x - cx) <= tol * 2 and abs(y - cy) <= tol * 2
    return ClickResult(ok, cx, cy, max_loops, "near" if ok else "miss", journal)


def click_xy(
    x: int,
    y: int,
    *,
    jac: Jacobian | None = None,
    double: bool = False,
) -> ClickResult:
    res = servo_to(x, y, jac=jac)
    if res.ok or res.reason == "near":
        set_cursor(x, y)
        time.sleep(0.03)
        _click_now(double=double)
        res.ok = True
        res.reason = "clicked"
    return res


def abs_from_frac(
    rect: tuple[int, int, int, int], rx: float, ry: float
) -> tuple[int, int]:
    l, t, r, b = rect
    return int(l + (r - l) * rx), int(t + (b - t) * ry)
