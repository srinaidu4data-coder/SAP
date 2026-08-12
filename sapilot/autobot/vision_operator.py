"""
VisionOperator — human-operator SAP GUI automation with NO dependency on SAP GUI
Scripting (sapgui/user_scripting). Real mouse + keyboard input only. Screen state
is read by an agent viewing screenshots (there is no OCR here) — this module's
job is to make the *action* side fast and reliable so the agent isn't burning
turns on misclicks. See VISION_OPERATOR_PLAYBOOK.md for the full write-up of why
each rule below exists — each one was a real, reproduced failure, not a guess.

Hard rules (from a live debugging session against a real SAP system):

1. SAP search-help popups (F4 dialogs, "Exit Document", message boxes) are
   SEPARATE top-level windows — not child regions of the main session window.
   A click computed as a fraction of the main window's rect will land in the
   wrong place once a popup is open. Always locate the popup with find_popup()
   and compute clicks against ITS OWN rect via Op.for_popup().

2. Use direct cursor jumps, not animated movement, for clicks inside SAP
   screens. An animated path crosses whatever sits between the old and new
   cursor position — including hover-sensitive elements (e.g. a Business
   Partner quick-info link) — and can trigger an unwanted popup mid-move.

3. Never call ShowWindow(SW_RESTORE) on a window that's already maximized —
   it silently un-maximizes it, which invalidates every relative coordinate
   computed against the "maximized" rect for the rest of the sequence.
   focus_window() in sapilot.connect.mouse already guards this; reuse it.

4. Field focus is NOT guaranteed on screen entry. Some screens auto-focus
   their first field (SE16N's "Data base" field, ME51N's Supplier field);
   others don't (SAP Easy Access after back-navigation lands focus on the
   tree, not the command field). Never assume — click the target field
   before typing unless you've verified auto-focus on that specific screen.

5. When a field rejects a value ("X is mandatory", "not found", "belongs to
   company code A, not B"), do not keep guessing values. Immediately look the
   real value up: open_table_browse() drives the whole SE16N round trip
   (command field -> /nSE16N -> table name -> F8 -> List Output) in one call
   instead of five, and returns a screenshot of real rows to read a valid
   value from. This is the "go back to tables" reflex — make it cheap enough
   that there's no reason not to reach for it on the first rejection.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from sapilot.connect.mouse import focus_window, mouse_enabled

log = logging.getLogger(__name__)

# Command field position is stable across SAP Easy Access / most classic dynpro
# screens in the modern (Fiori-themed) GUI, as a fraction of the session window.
COMMAND_FIELD_REL = (0.045, 0.118)


def _win32():
    import win32api  # type: ignore
    import win32con  # type: ignore
    import win32com.client  # type: ignore
    import win32gui  # type: ignore

    return win32api, win32con, win32com, win32gui


def find_sap_session() -> int:
    """Locate the main SAP_FRONTEND_SESSION window. Raises if none is open."""
    _, _, _, win32gui = _win32()
    found: list[int] = []

    def cb(h: int, _: Any) -> None:
        if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == "SAP_FRONTEND_SESSION":
            found.append(h)

    win32gui.EnumWindows(cb, None)
    if not found:
        raise RuntimeError(
            "No SAP_FRONTEND_SESSION window found. Is a system logged on in SAP Logon?"
        )
    return found[-1]


def find_popup(title_substr: str, *, exclude: int | None = None) -> int | None:
    """
    Locate a modal SAP popup (search-help, message box, Exit Document, etc.) by a
    substring of its title. These are separate top-level windows — see module
    docstring rule 1. Returns the most recently created match, or None.
    """
    _, _, _, win32gui = _win32()
    found: list[int] = []

    def cb(h: int, _: Any) -> None:
        if h == exclude or not win32gui.IsWindowVisible(h):
            return
        t = win32gui.GetWindowText(h)
        if title_substr.lower() in t.lower():
            found.append(h)

    win32gui.EnumWindows(cb, None)
    return found[-1] if found else None


def list_windows(substr: str = "") -> list[tuple[int, str, str]]:
    """Debug helper: list visible windows whose title or class contains substr."""
    _, _, _, win32gui = _win32()
    out: list[tuple[int, str, str]] = []

    def cb(h: int, _: Any) -> None:
        if not win32gui.IsWindowVisible(h):
            return
        t = win32gui.GetWindowText(h)
        c = win32gui.GetClassName(h)
        if not substr or substr.lower() in t.lower() or substr.lower() in c.lower():
            out.append((h, c, t))

    win32gui.EnumWindows(cb, None)
    return out


@dataclass
class FillStep:
    rx: float
    ry: float
    value: str = ""
    clear: bool = True
    key_after: str | None = None  # "ENTER" | "TAB" | None
    key_settle: float = 0.3  # bump this for keys that trigger a server round-trip
    pace: float = 0.05


@dataclass
class Op:
    """A target window (main session or a popup) plus the primitives to drive it."""

    hwnd: int
    shot_dir: str
    _shot_seq: list[int] = field(default_factory=lambda: [0])

    @classmethod
    def for_session(cls, shot_dir: str, hwnd: int | None = None) -> "Op":
        return cls(hwnd=hwnd or find_sap_session(), shot_dir=shot_dir)

    @classmethod
    def for_popup(cls, shot_dir: str, title_substr: str, *, exclude: int | None = None) -> "Op":
        h = find_popup(title_substr, exclude=exclude)
        if h is None:
            raise RuntimeError(f"No popup window matching {title_substr!r} found")
        return cls(hwnd=h, shot_dir=shot_dir)

    # -- geometry -----------------------------------------------------
    def rect(self) -> tuple[int, int, int, int]:
        _, _, _, win32gui = _win32()
        return win32gui.GetWindowRect(self.hwnd)

    def _abs(self, rx: float, ry: float) -> tuple[int, int]:
        left, top, right, bottom = self.rect()
        w, h = right - left, bottom - top
        return int(left + w * rx), int(top + h * ry)

    # -- focus ----------------------------------------------------------
    def focus(self, settle: float = 0.18) -> None:
        """
        Bring the window to front and give the remote SAP frontend a moment to
        catch up. NOTE: an earlier version of this skipped SetForegroundWindow
        entirely when the window was already foreground, to save time — that
        was wrong. The settle delay isn't about window activation, it's a
        buffer for the SAP GUI frontend (often talking to a remote backend) to
        actually be ready for the next input; skipping it caused clicks and
        keystrokes to silently land on/reach the wrong control. Always pay
        this small cost; don't skip it to chase speed.
        """
        focus_window(self.hwnd, settle=settle)

    # -- actions --------------------------------------------------------
    def click(self, rx: float, ry: float, *, settle: float = 0.18) -> tuple[int, int]:
        """Direct-jump click (no animated path — see module docstring rule 2)."""
        win32api, win32con, _, _ = _win32()
        self.focus(settle)
        x, y = self._abs(rx, ry)
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.03)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.12)
        return x, y

    def double_click(self, rx: float, ry: float, *, settle: float = 0.18) -> tuple[int, int]:
        """
        Some collapsible section headers (e.g. ME51N's "Item Overview") only
        expand on a genuine double-click — a single click, or two single clicks
        separated by enough time to not register as one, does nothing visible.
        """
        win32api, win32con, _, _ = _win32()
        self.focus(settle)
        x, y = self._abs(rx, ry)
        win32api.SetCursorPos((x, y))
        for _ in range(2):
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.03)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.06)
        time.sleep(0.12)
        return x, y

    def type(self, text: str, *, pace: float = 0.05, secret: bool = False) -> None:
        # SendKeys goes to whatever window the OS currently considers foreground —
        # which is NOT guaranteed to still be this one, especially across separate
        # process invocations (a terminal/chat app regaining focus between calls is
        # exactly how keystrokes silently ended up typed into the wrong window
        # entirely, not just misplaced on the right screen). Always re-focus before
        # sending any keys — never assume a prior click's focus is still current.
        self.focus()
        _, _, win32com, _ = _win32()
        shell = win32com.client.Dispatch("WScript.Shell")
        from sapilot.connect.logon import _escape_sendkeys

        for ch in text:
            shell.SendKeys(_escape_sendkeys(ch))
            time.sleep(pace)
        log.debug("typed %r", "***" if secret else text)

    def clear(self) -> None:
        self.focus()
        _, _, win32com, _ = _win32()
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.SendKeys("^a")
        time.sleep(0.04)
        shell.SendKeys("{DEL}")
        time.sleep(0.04)

    def key(self, name: str, *, settle: float = 0.3) -> None:
        self.focus()
        _, _, win32com, _ = _win32()
        win32com.client.Dispatch("WScript.Shell").SendKeys("{" + name + "}")
        time.sleep(settle)

    def screenshot(self, name: str | None = None, *, ensure_focus: bool = True) -> str:
        """
        Capture this window. ensure_focus=True (default) brings it to front first —
        a screenshot of a window that isn't actually on top captures whatever IS on
        top instead (this was a real bug: an unfocused SAP window's rect was
        captured and it silently returned a screenshot of an unrelated browser tab
        sitting on top of it). Only pass ensure_focus=False when you've already
        focused deliberately and stealing focus again would be wrong (rare).
        """
        from PIL import ImageGrab

        if ensure_focus:
            self.focus()
        if name is None:
            self._shot_seq[0] += 1
            name = f"shot_{self._shot_seq[0]:03d}"
        img = ImageGrab.grab(bbox=self.rect(), all_screens=True)
        path = f"{self.shot_dir}\\{name}.png"
        img.save(path)
        return path

    # -- batched multi-field entry ---------------------------------------
    def fill(self, steps: list[FillStep], *, shot_name: str | None = None) -> str:
        """
        Execute several field fills back-to-back and return ONE screenshot at the
        end, instead of round-tripping a screenshot per field. This is the main
        speed lever: an agent should batch every field it's confident about into
        a single fill() call and only screenshot to check the result or when a
        field's correct position is genuinely uncertain.
        """
        for step in steps:
            self.click(step.rx, step.ry)
            if step.clear:
                self.clear()
            if step.value:
                self.type(step.value, pace=step.pace)
            if step.key_after:
                self.key(step.key_after, settle=step.key_settle)
        return self.screenshot(shot_name)


# ---------------------------------------------------------------------------
# High-level recipes — validated, multi-step flows collapsed into one call.
# ---------------------------------------------------------------------------


def goto_transaction(op: Op, tcode: str, *, shot_name: str | None = None) -> str:
    """Click the command field, enter /nTCODE, and return a screenshot of the result."""
    op.click(*COMMAND_FIELD_REL)
    op.clear()
    op.type(f"/n{tcode.upper()}", pace=0.08)
    op.key("ENTER", settle=1.3)
    return op.screenshot(shot_name)


def open_table_browse(op: Op, table: str, *, shot_name: str | None = None) -> str:
    """
    The validated SE16N round trip, in one call: command field -> /nSE16N ->
    Data base field (auto-focused on that screen) -> table name -> F8 (validates
    the table name and reveals "List Output") -> click List Output -> screenshot
    of the resulting grid.

    This is the "go back to tables" reflex from module docstring rule 5: reach
    for this the FIRST time a field rejects a value, not after several guesses.
    """
    op.click(*COMMAND_FIELD_REL)
    op.clear()
    op.type("/nSE16N", pace=0.08)
    op.key("ENTER", settle=1.2)
    # Data base field is auto-focused on a fresh SE16N screen — no click needed.
    for ch in table.upper():
        op.type(ch, pace=0.11)
    op.key("F8", settle=1.0)
    # "List Output" button appears bottom-left once the table name validates.
    op.click(0.0275, 0.961, settle=0.3)
    time.sleep(1.2)
    return op.screenshot(shot_name)


def back_out(op: Op, times: int = 1, *, settle: float = 0.8) -> None:
    """Press F3 (SAP 'Back') the given number of times — the safe, non-destructive exit."""
    for _ in range(times):
        op.key("F3", settle=settle)
