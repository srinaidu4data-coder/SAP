"""Recover from SAP glass errors: detect, back out, retry. Never Save."""
from __future__ import annotations

import time
from typing import Any

from sapilot.display.policy import is_create_screen
from sapilot.autobot.vision_operator import Op, find_popup

# Title fragments that prove we landed on the intended display t-code.
SCREEN_HINTS: dict[str, tuple[str, ...]] = {
    "SE16N": ("general table display", "se16n"),
    "SE16": ("data browser", "se16"),
    "SESSION_MANAGER": ("easy access",),
    "VA03": ("display sales", "sales document"),
    "VF03": ("display billing", "billing document"),
    "VL03N": ("display outbound", "display delivery"),
    "FB03": ("display document",),
    "FBL5N": ("customer line", "line item"),
    "FBL1N": ("vendor line", "line item"),
    "FBL3N": ("g/l line", "line item"),
    "FARR_RAI_MON": ("revenue accounting", "rai"),
    "MM03": ("display material",),
    "XD03": ("customer display", "display customer"),
    "ME23N": ("display purchase", "purchase order"),
    "CK13N": ("display cost",),
    "KS03": ("display cost center",),
}

# Status / OCR that means the last action was a navigation mistake — back out and retry.
_RETRY_ERR = (
    "is not created in language",
    "unit ",
    "not a valid value",
    "choose a valid",
    "fill in all required",
    "required entry",
    "invalid entry",
    "input should be",
    "entry is too long",
    "not a window",
    "session not found",
    "transaction cannot be started",
    "transaction is locked",
)

# Real findings — do not treat as a nav failure.
_GIVE_UP = (
    "does not exist",
    "unknown table",
    "invalid table",
    "not authorized",
    "no authorization",
    "you are not authorized",
    "no values found",
)


def screen_text(hh) -> tuple[str, str, str]:
    title = ""
    status = ""
    blob = ""
    try:
        title = hh._title() or ""
    except Exception:
        title = ""
    try:
        view = hh.see("nav_probe")
        if view and view.status:
            status = view.status.text or ""
        blob = " ".join(w.text for w in (view.words or [])) if view else ""
    except Exception:
        pass
    return title, status, blob


def classify(title: str, status: str = "", blob: str = "", expect: str | None = None) -> dict[str, Any]:
    """Decide what the glass is, without touching SAP."""
    t = (title or "").strip()
    low = t.lower()
    body = f"{status} {blob}".lower()
    kind = "tx"
    if "easy access" in low:
        kind = "menu"
    elif t.strip() in {"SAP", ""}:
        kind = "shell"
    elif "general table display" in low or "se16n" in low:
        kind = "se16n"
    elif is_create_screen(t, status):
        kind = "create"
    error = None
    retry = False
    if any(tok in body for tok in _GIVE_UP) and "is not created in language" not in body:
        error = "finding"
    elif any(tok in body for tok in _RETRY_ERR):
        error = "nav"
        retry = True
        kind = "error"
    expect_ok = True
    code = (expect or "").upper()
    if code:
        hints = SCREEN_HINTS.get(code)
        if hints:
            expect_ok = any(h in low for h in hints)
        elif kind == "shell":
            expect_ok = False
        if code == "SE16N" and kind != "se16n":
            expect_ok = False
        if code == "SESSION_MANAGER" and kind != "menu":
            expect_ok = False
    if kind in {"create", "shell"}:
        expect_ok = False
    return {
        "kind": kind,
        "title": t,
        "status": status or "",
        "expect_ok": expect_ok,
        "error": error,
        "retry": retry,
    }


def dismiss(hh) -> int:
    """Close dialogs. Cancel / X only. Never Save or Finish."""
    closed = 0
    op = hh._op()
    for title in (
        "Entries",
        "Number of",
        "Technical Settings",
        "Messages",
        "Information",
        "Error",
        "Warning",
        "Shortcut",
        "Create New",
        "SAP Shortcut",
        "Personal Settings",
        "SAP GUI Security",
    ):
        pop = find_popup(title, exclude=op.hwnd)
        if not pop:
            continue
        popop = Op(hwnd=pop, shot_dir=hh.shot_dir)
        # Cancel cluster is left of Finish/Save on SAP dialogs.
        popop.click(0.52, 0.90, settle=0.2)
        time.sleep(0.15)
        popop.click(0.97, 0.14, settle=0.15)
        closed += 1
    return closed


def back_out(hh, steps: int = 2) -> None:
    """Leave a bad dynpro. F12 cancel, F3 back. Never F11 / Ctrl+S."""
    dismiss(hh)
    try:
        hh.key("ESCAPE", settle=0.35)
    except Exception:
        pass
    for _ in range(max(1, steps)):
        try:
            hh.key("F12", settle=0.45)
        except Exception:
            pass
        try:
            hh.key("F3", settle=0.5)
        except Exception:
            pass
        title = ""
        try:
            title = hh._title() or ""
        except Exception:
            break
        kind = classify(title).get("kind")
        if kind in {"menu", "se16n", "shell"}:
            break


def rebind(hh) -> bool:
    """Dead hwnd — find the live SAP session again."""
    hh.hwnd = None
    try:
        op = hh._op()
        hh.hwnd = op.hwnd
        return True
    except Exception:
        try:
            from sapilot.autobot.vision_operator import find_sap_session

            hh.hwnd = find_sap_session()
            return True
        except Exception:
            return False


def reset_menu(hh) -> bool:
    """Easy Access. Safe place to start any display t-code."""
    dismiss(hh)
    title = ""
    try:
        title = hh._title() or ""
    except Exception:
        if not rebind(hh):
            return False
        title = hh._title() or ""
    if "easy access" in title.lower():
        return True
    if classify(title).get("kind") == "shell":
        try:
            hh._leave_blank_shell()
        except Exception:
            pass
        title = hh._title() or ""
        if "easy access" in title.lower():
            return True
    back_out(hh, steps=2)
    title = hh._title() or ""
    if "easy access" in title.lower():
        return True
    try:
        hh.goto("SESSION_MANAGER")
    except Exception:
        if not rebind(hh):
            return False
        try:
            hh.goto("SESSION_MANAGER")
        except Exception:
            return False
    time.sleep(0.4)
    title = hh._title() or ""
    if classify(title).get("kind") == "shell":
        try:
            hh._leave_blank_shell()
        except Exception:
            pass
    return "easy access" in (hh._title() or "").lower()


def goto_checked(hh, tcode: str, *, retries: int = 2) -> dict[str, Any]:
    """Goto a display t-code. If the title is wrong or an error fires, back out and retry."""
    code = (tcode or "").strip().upper()
    last = classify("", expect=code)
    for attempt in range(retries + 1):
        try:
            dismiss(hh)
            if attempt:
                reset_menu(hh)
            r = hh.goto(code)
            time.sleep(0.35)
            title, status, blob = screen_text(hh)
            rec = classify(title, status, blob, expect=code)
            rec["attempt"] = attempt + 1
            rec["ok"] = bool(rec.get("expect_ok")) and rec.get("kind") != "create"
            if rec.get("kind") == "create":
                back_out(hh, steps=2)
                last = rec
                continue
            if rec.get("retry") or not rec.get("expect_ok"):
                back_out(hh, steps=1)
                last = rec
                continue
            rec["detail"] = r.detail if hasattr(r, "detail") else title
            try:
                from sapilot.learn.policy import remember

                remember(
                    title,
                    status,
                    blob,
                    "goto",
                    {"kind": "goto", "tcode": code},
                    1 if rec.get("ok") else -1,
                    note=title,
                )
            except Exception:
                pass
            return rec
        except Exception as e:
            last = classify("", str(e), str(e), expect=code)
            last["ok"] = False
            last["attempt"] = attempt + 1
            last["detail"] = str(e)[:180]
            last["retry"] = True
            if "not a window" in str(e).lower() or "session" in str(e).lower():
                rebind(hh)
            else:
                try:
                    back_out(hh, steps=1)
                except Exception:
                    rebind(hh)
    last["ok"] = False
    return last


def ensure_screen(hh, tcode: str, *, retries: int = 2) -> dict[str, Any]:
    title, status, blob = screen_text(hh)
    rec = classify(title, status, blob, expect=tcode)
    if rec.get("expect_ok") and rec.get("kind") != "create":
        rec["ok"] = True
        rec["attempt"] = 0
        return rec
    if rec.get("kind") == "create" or rec.get("retry"):
        back_out(hh, steps=2)
    return goto_checked(hh, tcode, retries=retries)
