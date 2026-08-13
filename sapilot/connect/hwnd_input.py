"""
Process-scoped SAP GUI input — no OS-wide SendKeys, no window-fraction ok-code.

Binds one SAP_FRONTEND_SESSION by hwnd + pid, finds the toolbar command field
as a real child control (name / class / toolbar geometry — never a hardcoded
fraction), and types with WM_SETTEXT or SendInput only while that SAP process
owns the foreground.

Fail closed if the session or ok-code control cannot be identified.
"""

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

# IAccessible / UIA name fragments that identify the command field.
OKCD_NAME_HINTS = (
    "command",
    "ok-code",
    "ok code",
    "okcode",
    "ok_code",
    "transaction",
    "okcd",
)
EDIT_CLASS_HINTS = ("edit", "sapfedt", "richedit", "afx:")
# Name-match alone, or edit-in-toolbar-left, must clear this.
MIN_OKCD_SCORE = 45

_VK = {
    "ENTER": 0x0D,
    "RETURN": 0x0D,
    "TAB": 0x09,
    "ESC": 0x1B,
    "ESCAPE": 0x1B,
    "BACK": 0x08,
    "BACKSPACE": 0x08,
    "DELETE": 0x2E,
    "DEL": 0x2E,
    "F2": 0x71,
    "F3": 0x72,
    "F4": 0x73,
    "F5": 0x74,
    "F6": 0x75,
    "F7": 0x76,
    "F8": 0x77,
    "F11": 0x7A,
    "F12": 0x7B,
    "PAGEDOWN": 0x22,
    "PAGEUP": 0x21,
}

WM_SETTEXT = 0x000C
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1
VK_CONTROL = 0x11
VK_A = 0x41


class OkcdNotFound(RuntimeError):
    """Command field could not be identified — refuse to type a tcode."""


class SessionNotFound(RuntimeError):
    """No SAP_FRONTEND_SESSION to bind (or more than one and none is focused)."""


class ForegroundLost(RuntimeError):
    """SAP session is not the foreground window; refusing OS-wide key injection."""


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def w(self) -> int:
        return max(self.right - self.left, 0)

    @property
    def h(self) -> int:
        return max(self.bottom - self.top, 0)


@dataclass(frozen=True)
class ChildInfo:
    hwnd: int
    class_name: str
    title: str
    rect: Rect
    acc_name: str = ""
    automation_id: str = ""


def score_okcd_candidate(child: ChildInfo, parent: Rect) -> int:
    """Pure scoring — unit-tested without win32."""
    score = 0
    name = f"{child.acc_name} {child.title} {child.automation_id}".lower()
    cls = (child.class_name or "").lower()
    if any(h in name for h in OKCD_NAME_HINTS):
        score += 50
    if any(h in cls for h in EDIT_CLASS_HINTS):
        score += 15
    pw = max(parent.w, 1)
    ph = max(parent.h, 1)
    rel_x = (child.rect.left - parent.left) / pw
    rel_y = (child.rect.top - parent.top) / ph
    rel_w = child.rect.w / pw
    rel_h = child.rect.h / ph
    if 0.0 <= rel_y < 0.18:
        score += 20
    if 0.0 <= rel_x < 0.45:
        score += 10
    if 0.04 <= rel_w <= 0.38:
        score += 10
    if 0.008 <= rel_h <= 0.09:
        score += 5
    return score


def pick_okcd(children: list[ChildInfo], parent: Rect) -> ChildInfo | None:
    if not children:
        return None
    ranked = sorted(
        ((score_okcd_candidate(c, parent), c) for c in children),
        key=lambda t: t[0],
        reverse=True,
    )
    best_score, best = ranked[0]
    if best_score < MIN_OKCD_SCORE:
        return None
    return best


def _win32() -> tuple[Any, Any, Any]:
    import win32gui  # type: ignore
    import win32process  # type: ignore

    from sapilot.connect.mouse import focus_window

    return win32gui, win32process, focus_window


def _window_rect(hwnd: int) -> Rect:
    win32gui, _, _ = _win32()
    l, t, r, b = win32gui.GetWindowRect(hwnd)
    return Rect(l, t, r, b)


def _pid_of(hwnd: int) -> int:
    _, win32process, _ = _win32()
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return int(pid)


def _acc_name(hwnd: int) -> str:
    """Best-effort IAccessible name via oleacc. Empty on any failure."""
    try:
        oleacc = ctypes.oledll.oleacc  # type: ignore[attr-defined]
    except Exception:
        return ""
    try:
        import comtypes  # type: ignore
        import comtypes.automation  # type: ignore
        import comtypes.client  # type: ignore

        OBJID_CLIENT = 0xFFFFFFFC
        iid = comtypes.GUID("{618736E0-3C3D-11CF-810C-00AA00389B71}")
        ptr = ctypes.POINTER(comtypes.automation.IDispatch)()
        hr = oleacc.AccessibleObjectFromWindow(
            wintypes.HWND(hwnd),
            ctypes.c_uint(OBJID_CLIENT),
            ctypes.byref(iid),
            ctypes.byref(ptr),
        )
        if hr != 0 or not ptr:
            return ""
        acc = comtypes.client.GetBestInterface(ptr)
        name = acc.accName(0)
        return str(name or "")
    except Exception:
        return ""


def _enum_children(hwnd: int) -> list[ChildInfo]:
    win32gui, _, _ = _win32()
    found: list[int] = []

    def cb(h: int, _: Any) -> None:
        found.append(h)

    try:
        win32gui.EnumChildWindows(hwnd, cb, None)
    except Exception:
        return []
    out: list[ChildInfo] = []
    for h in found:
        try:
            if not win32gui.IsWindowVisible(h):
                continue
            cls = win32gui.GetClassName(h) or ""
            title = win32gui.GetWindowText(h) or ""
            rect = _window_rect(h)
            if rect.w <= 1 or rect.h <= 1:
                continue
            out.append(
                ChildInfo(
                    hwnd=h,
                    class_name=cls,
                    title=title,
                    rect=rect,
                    acc_name=_acc_name(h),
                )
            )
        except Exception:
            continue
    return out


def find_okcd_hwnd(session_hwnd: int) -> int:
    parent = _window_rect(session_hwnd)
    children = _enum_children(session_hwnd)
    picked = pick_okcd(children, parent)
    if picked is None:
        raise OkcdNotFound(
            "Could not identify the SAP command field (okcd). "
            "Refusing to type a tcode into an unknown control. "
            f"Inspected {len(children)} child windows."
        )
    log.info(
        "okcd hwnd=%s class=%s acc=%r score-pick",
        picked.hwnd,
        picked.class_name,
        picked.acc_name or picked.title,
    )
    return picked.hwnd


def list_sessions() -> list[tuple[int, int, str]]:
    """Visible SAP_FRONTEND_SESSION windows as (hwnd, pid, title)."""
    win32gui, _, _ = _win32()
    out: list[tuple[int, int, str]] = []

    def cb(h: int, _: Any) -> None:
        if not win32gui.IsWindowVisible(h):
            return
        if win32gui.GetClassName(h) != "SAP_FRONTEND_SESSION":
            return
        out.append((h, _pid_of(h), win32gui.GetWindowText(h) or ""))

    win32gui.EnumWindows(cb, None)
    return out


def bind_window(hwnd: int) -> "SapHwndSession":
    """Bind any window (session or popup) by hwnd + pid. No class filter."""
    win32gui, _, _ = _win32()
    if not win32gui.IsWindow(hwnd):
        raise SessionNotFound(f"hwnd {hwnd} is not a window")
    return SapHwndSession(
        hwnd=hwnd,
        pid=_pid_of(hwnd),
        title=win32gui.GetWindowText(hwnd) or "",
    )


def bind_session(hwnd: int | None = None) -> "SapHwndSession":
    """
    Bind exactly one session.

    Rules:
      - class must be SAP_FRONTEND_SESSION (never title.startswith('SAP'))
      - if hwnd given, verify class and take its pid
      - if the foreground window is a session, use that
      - if exactly one session exists, use it
      - otherwise fail closed (do not pick found[-1] or 'Easy Access' by title)
    """
    win32gui, _, _ = _win32()
    sessions = list_sessions()
    if hwnd is not None:
        if not win32gui.IsWindow(hwnd):
            raise SessionNotFound(f"hwnd {hwnd} is not a window")
        if win32gui.GetClassName(hwnd) != "SAP_FRONTEND_SESSION":
            raise SessionNotFound(
                f"hwnd {hwnd} class is {win32gui.GetClassName(hwnd)!r}, "
                "not SAP_FRONTEND_SESSION"
            )
        title = win32gui.GetWindowText(hwnd) or ""
        return SapHwndSession(hwnd=hwnd, pid=_pid_of(hwnd), title=title)

    if not sessions:
        raise SessionNotFound(
            "No SAP_FRONTEND_SESSION window found. Log on in SAP GUI first."
        )

    try:
        fg = int(win32gui.GetForegroundWindow())
    except Exception:
        fg = 0
    for h, pid, title in sessions:
        if h == fg:
            return SapHwndSession(hwnd=h, pid=pid, title=title)
    # Foreground may be a child of the session (popup / edit).
    if fg:
        try:
            fg_pid = _pid_of(fg)
        except Exception:
            fg_pid = 0
        same = [(h, pid, title) for h, pid, title in sessions if pid == fg_pid]
        if len(same) == 1:
            h, pid, title = same[0]
            return SapHwndSession(hwnd=h, pid=pid, title=title)

    if len(sessions) == 1:
        h, pid, title = sessions[0]
        return SapHwndSession(hwnd=h, pid=pid, title=title)

    titles = ", ".join(f"{h}:{t!r}" for h, _, t in sessions[:6])
    raise SessionNotFound(
        f"{len(sessions)} SAP sessions are open and none is focused. "
        f"Focus the session you want, then retry. Sessions: {titles}"
    )


def _same_process_foreground(session_hwnd: int, pid: int) -> bool:
    win32gui, _, _ = _win32()
    fg = int(win32gui.GetForegroundWindow())
    if fg == session_hwnd:
        return True
    try:
        return _pid_of(fg) == pid
    except Exception:
        return False


def _ensure_foreground(session_hwnd: int, pid: int, *, settle: float = 0.12) -> None:
    _, _, focus_window = _win32()
    if _same_process_foreground(session_hwnd, pid):
        return
    for _ in range(4):
        focus_window(session_hwnd, settle=settle)
        if _same_process_foreground(session_hwnd, pid):
            return
        time.sleep(0.15)
    raise ForegroundLost(
        "SAP session is not the foreground window; refusing SendInput "
        "so keystrokes cannot land in another app. Click the SAP window once."
    )


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    )


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    )


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = (
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    )


class _INPUTUNION(ctypes.Union):
    _fields_ = (("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT), ("hi", _HARDWAREINPUT))


class _INPUT(ctypes.Structure):
    _fields_ = (("type", wintypes.DWORD), ("union", _INPUTUNION))


def _send_vk(vk: int, *, up: bool = False) -> None:
    extra = ctypes.pointer(ctypes.c_ulong(0))
    inp = _INPUT()
    inp.type = INPUT_KEYBOARD
    inp.union.ki.wVk = vk
    inp.union.ki.wScan = 0
    inp.union.ki.dwFlags = KEYEVENTF_KEYUP if up else 0
    inp.union.ki.time = 0
    inp.union.ki.dwExtraInfo = extra
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def _send_unicode_char(ch: str) -> None:
    extra = ctypes.pointer(ctypes.c_ulong(0))
    for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
        inp = _INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wVk = 0
        inp.union.ki.wScan = ord(ch)
        inp.union.ki.dwFlags = flags
        inp.union.ki.time = 0
        inp.union.ki.dwExtraInfo = extra
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def send_key_name(name: str) -> None:
    key = (name or "").strip().upper()
    if key not in _VK:
        raise ValueError(
            f"Unknown key {name!r}. Allowed: {', '.join(sorted(_VK))}."
        )
    vk = _VK[key]
    _send_vk(vk, up=False)
    time.sleep(0.01)
    _send_vk(vk, up=True)


def send_text_unicode(text: str) -> None:
    for ch in text:
        _send_unicode_char(ch)


def _set_window_text(hwnd: int, text: str) -> None:
    ctypes.windll.user32.SendMessageW(hwnd, WM_SETTEXT, 0, text)


def _post_enter(hwnd: int) -> None:
    user32 = ctypes.windll.user32
    user32.PostMessageW(hwnd, WM_KEYDOWN, _VK["ENTER"], 0)
    user32.PostMessageW(hwnd, WM_CHAR, _VK["ENTER"], 0)
    user32.PostMessageW(hwnd, WM_KEYUP, _VK["ENTER"], 0xC0000001)


@dataclass
class SapHwndSession:
    hwnd: int
    pid: int
    title: str
    _okcd: int | None = None

    def okcd_hwnd(self) -> int:
        if self._okcd:
            try:
                win32gui, _, _ = _win32()
                if win32gui.IsWindow(self._okcd):
                    return self._okcd
            except Exception:
                pass
        self._okcd = find_okcd_hwnd(self.hwnd)
        return self._okcd

    def focus(self, settle: float = 0.12) -> None:
        _ensure_foreground(self.hwnd, self.pid, settle=settle)

    def start_transaction(self, tcode: str) -> None:
        """
        Put /nTCODE in the real command field and press Enter.
        Types via SendInput (WM_SETTEXT drops the leading / on this GUI).
        Never clicks a window fraction. Fails closed if okcd is not found.
        """
        raw = (tcode or "").strip()
        for prefix in ("/N", "/O", "/n", "/o"):
            if raw.upper().startswith(prefix):
                raw = raw[len(prefix) :]
                break
        code = raw.strip().lstrip("/").strip().upper()
        if not code:
            raise ValueError("empty tcode")
        okcd = self.okcd_hwnd()
        self.focus(settle=0.1)
        try:
            import win32api  # type: ignore
            import win32con  # type: ignore
            import win32gui  # type: ignore

            win32gui.SetFocus(okcd)
            l, t, r, b = win32gui.GetWindowRect(okcd)
            win32api.SetCursorPos(((l + r) // 2, (t + b) // 2))
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.03)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        except Exception:
            pass
        time.sleep(0.08)
        self.clear_field()
        send_text_unicode(f"/n{code}")
        time.sleep(0.04)
        _post_enter(okcd)
        if _same_process_foreground(self.hwnd, self.pid):
            send_key_name("ENTER")
        time.sleep(1.15)
        log.info("hwnd start_transaction %s hwnd=%s pid=%s", code, self.hwnd, self.pid)

    def save(self) -> None:
        """SAP Save: F11 (standard), then Ctrl+S (Enjoy/Fiori themes)."""
        self.focus(settle=0.08)
        send_key_name("F11")
        time.sleep(0.4)
        if _same_process_foreground(self.hwnd, self.pid):
            _send_vk(VK_CONTROL, up=False)
            _send_vk(0x53, up=False)
            time.sleep(0.03)
            _send_vk(0x53, up=True)
            _send_vk(VK_CONTROL, up=True)
        time.sleep(1.2)
        log.info("hwnd save hwnd=%s", self.hwnd)

    def find_content_edit(self, *, exclude: int | None = None) -> int | None:
        """First wide Edit in the upper content band — SE16N 'Data base', not okcd."""
        parent = _window_rect(self.hwnd)
        okcd = exclude
        try:
            okcd = okcd or self.okcd_hwnd()
        except OkcdNotFound:
            okcd = None
        best: tuple[int, ChildInfo] | None = None
        for child in _enum_children(self.hwnd):
            if child.hwnd == okcd:
                continue
            if "edit" not in (child.class_name or "").lower():
                continue
            ph = max(parent.h, 1)
            pw = max(parent.w, 1)
            rel_y = (child.rect.top - parent.top) / ph
            rel_x = (child.rect.left - parent.left) / pw
            if not (0.12 <= rel_y <= 0.40 and 0.04 <= rel_x <= 0.45):
                continue
            if child.rect.w < 80:
                continue
            score = child.rect.w - int(rel_y * 200)
            if best is None or score > best[0]:
                best = (score, child)
        return best[1].hwnd if best else None

    def set_control_text(self, ctrl_hwnd: int, text: str) -> None:
        self.focus(settle=0.08)
        try:
            import win32gui  # type: ignore

            win32gui.SetFocus(ctrl_hwnd)
        except Exception:
            pass
        _set_window_text(ctrl_hwnd, text)
        time.sleep(0.05)

    def type_text(self, text: str, *, secret: bool = False, clear: bool = False) -> None:
        """Type into the currently focused control inside this SAP process."""
        self.focus(settle=0.08)
        if clear:
            self.clear_field()
        send_text_unicode(text)
        log.debug("hwnd typed %r", "***" if secret else text[:40])

    def clear_field(self) -> None:
        self.focus(settle=0.06)
        _send_vk(VK_CONTROL, up=False)
        _send_vk(VK_A, up=False)
        _send_vk(VK_A, up=True)
        _send_vk(VK_CONTROL, up=True)
        time.sleep(0.03)
        send_key_name("DELETE")
        time.sleep(0.03)

    def send_key(self, name: str) -> None:
        self.focus(settle=0.08)
        send_key_name(name)
        log.debug("hwnd key %s", name)
