"""
Human-like operator layer (COM-first, safe navigation).

CRITICAL: Transaction codes must NEVER be typed into data fields (e.g. Supplier).
  Wrong: click form field + type /nF110  → "Vendor /NF110 has not been created"
  Right: session.StartTransaction("F110") or ok-code toolbar field only
"""

from __future__ import annotations

import logging
import random
import re
import time
from typing import Any

log = logging.getLogger(__name__)

# Data-field names that must never receive a tcode string
_DATA_FIELD_MARKERS = (
    "LIFNR",
    "SUPPLIER",
    "VENDOR",
    "MATNR",
    "EBELN",
    "BANFN",
    "BELNR",
    "BUKRS",
    "RF02K",
    "PARTNER",
)


def human_pause(a: float = 0.12, b: float = 0.45) -> None:
    time.sleep(random.uniform(a, b))


def _looks_like_tcode_command(text: str) -> bool:
    """True for /nF110, /oME23N, F110 — False for vendor numbers like 0000100001."""
    t = (text or "").strip().upper()
    if t.startswith("/N") or t.startswith("/O"):
        return True
    # Pure digits = business key (vendor, PO, material), not a tcode
    if t.isdigit():
        return False
    # Short alphanumeric tcodes e.g. F110, ME23N, XK03, MIGO
    return bool(re.fullmatch(r"[A-Z][A-Z0-9_]{1,19}", t))



class HumanOperator:
    """Acts like a consultant — safe ok-code navigation + optional mouse."""

    def __init__(self, show_mouse: bool = True):
        import os

        if show_mouse:
            os.environ["SAPILOT_SHOW_MOUSE"] = "1"
        self.show_mouse = show_mouse
        self.actions: list[dict[str, Any]] = []
        self._session = None  # live COM session if available

    def log_action(self, kind: str, **kw: Any) -> None:
        rec = {"kind": kind, **kw, "ts": time.time()}
        self.actions.append(rec)
        log.info("HUMAN %s %s", kind, {k: v for k, v in kw.items() if k != "password"})

    def bind_session(self, session: Any) -> None:
        """Attach live SAP GUI Scripting session for correct navigation."""
        self._session = session
        self.log_action("bind_session")

    def try_bind_open_session(self) -> bool:
        """Pick up first scriptable session from running SAP GUI (fast-fail)."""
        import os

        offline = os.environ.get("SAPILOT_OFFLINE", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        if offline:
            self.log_action("bind_skipped", reason="SAPILOT_OFFLINE=1 CI mode")
            return False
        # Product default: try COM (LIVE_GUI defaults on). Explicit 0 disables.
        live_raw = os.environ.get("SAPILOT_LIVE_GUI", "1").strip().lower()
        live = live_raw not in {"0", "false", "no"}
        force = os.environ.get("SAPILOT_FORCE_COM_BIND", "1").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        if not live and not force:
            self.log_action("bind_skipped", reason="SAPILOT_LIVE_GUI=0")
            return False
        try:
            import win32com.client  # type: ignore

            sap = win32com.client.GetObject("SAPGUI")
            app = sap.GetScriptingEngine
            nconn = int(app.Children.Count)
            for ci in range(nconn):
                conn = app.Children(ci)
                nses = int(conn.Children.Count)
                for si in range(nses):
                    self._session = conn.Children(si)
                    try:
                        _ = self._session.Info.SystemName
                    except Exception:
                        self._session = None
                        continue
                    self.log_action("bound_open_session", conn=ci, ses=si)
                    return True
        except Exception as e:
            self.log_action("bind_fail", error=str(e)[:200])
            self._session = None
        return False

    def move_and_click(self, x: int, y: int) -> None:
        from sapilot.connect.mouse import click

        click(x, y)
        self.log_action("click", x=x, y=y)
        human_pause()

    def type_text(self, text: str, *, secret: bool = False) -> None:
        import win32com.client  # type: ignore

        from sapilot.connect.logon import _escape_sendkeys

        shell = win32com.client.Dispatch("WScript.Shell")
        shell.SendKeys(_escape_sendkeys(text))
        self.log_action("type", text="***" if secret else text[:40])
        human_pause(0.08, 0.2)

    def press_enter(self) -> None:
        import win32com.client  # type: ignore

        win32com.client.Dispatch("WScript.Shell").SendKeys("{ENTER}")
        self.log_action("enter")
        human_pause()

    def press_escape(self) -> None:
        import win32com.client  # type: ignore

        win32com.client.Dispatch("WScript.Shell").SendKeys("{ESC}")
        self.log_action("escape")
        human_pause(0.1, 0.25)

    def focus_sap(self) -> int | None:
        import win32gui  # type: ignore

        from sapilot.connect.mouse import focus_window

        found: list[int] = []

        def cb(h: int, _: Any) -> None:
            if not win32gui.IsWindowVisible(h):
                return
            cls = win32gui.GetClassName(h)
            title = win32gui.GetWindowText(h)
            if cls == "SAP_FRONTEND_SESSION" or "SAP Easy Access" in title or title.startswith("SAP"):
                found.append(h)

        win32gui.EnumWindows(cb, None)
        if not found:
            return None
        hwnd = found[0]
        for h in found:
            t = win32gui.GetWindowText(h)
            if "Easy Access" in t:
                hwnd = h
                break
        focus_window(hwnd)
        self.log_action("focus_sap", hwnd=hwnd, title=win32gui.GetWindowText(hwnd))
        return hwnd

    def start_transaction(self, tcode: str) -> bool:
        """
        Navigate to a tcode the CORRECT way.

        Priority:
          1) COM StartTransaction (never touches Supplier/Vendor fields)
          2) COM ok-code toolbar field only (wnd[0]/tbar[0]/okcd)
          3) Refuse random form clicks (prevents /nF110 in Supplier)
        """
        tcode = (tcode or "").strip().lstrip("/n/N/o/O").strip()
        if not tcode:
            return False

        # Always try (re)bind
        if self._session is None:
            self.try_bind_open_session()

        if self._session is not None:
            try:
                # Clean any bad value that may be sitting in a focused field — use COM only
                self._session.StartTransaction(Transaction=tcode)
                human_pause(0.35, 0.7)
                self.log_action("start_transaction_com", tcode=tcode)
                return True
            except Exception as e1:
                self.log_action("start_transaction_com_fail", error=str(e1))
                try:
                    okcd = self._session.FindById("wnd[0]/tbar[0]/okcd")
                    # Mouse onto REAL ok-code control only
                    if self.show_mouse:
                        try:
                            from sapilot.connect.mouse import click_sap_component

                            click_sap_component(okcd)
                        except Exception:
                            pass
                    okcd.Text = f"/n{tcode}"
                    self._session.FindById("wnd[0]").SendVKey(0)
                    human_pause(0.35, 0.7)
                    self.log_action("okcode_com", tcode=tcode)
                    return True
                except Exception as e2:
                    self.log_action("okcode_com_fail", error=str(e2))

        # Unsafe keyboard fallback REMOVED for tcode entry into arbitrary clicks.
        # Typing /nXXX after clicking ~12%,6% of window landed in Supplier on BP screens.
        self.log_action(
            "okcode_refused_unsafe",
            tcode=tcode,
            reason="No scriptable session — will not type tcode into form fields",
        )
        return False

    def type_okcode(self, tcode: str) -> None:
        """Backward-compatible name — always uses safe start_transaction."""
        ok = self.start_transaction(tcode)
        if not ok:
            log.warning(
                "Could not navigate to %s safely. Enable SAP GUI scripting "
                "(sapgui/user_scripting=TRUE) so bot uses command field / StartTransaction.",
                tcode,
            )

    def fill_field_com(self, field_name: str, value: str) -> bool:
        """Set a data field by name via COM — never used for tcodes. Hard-abort path available."""
        if self._session is None and not self.try_bind_open_session():
            return False
        # Mission-critical precision: hard block (and optional raise) on tcode pollution
        try:
            from sapilot.mission.precision import assert_never_tcode_in_data_field

            assert_never_tcode_in_data_field(field_name, value)
        except Exception as e:
            self.log_action("blocked_tcode_in_data_field", field=field_name, value=value, err=str(e))
            return False
        if _looks_like_tcode_command(value) and any(
            m in field_name.upper() for m in _DATA_FIELD_MARKERS
        ):
            self.log_action("blocked_tcode_in_data_field", field=field_name, value=value)
            return False
        candidates = [
            field_name,
            f"wnd[0]/usr/ctxt{field_name}",
            f"wnd[0]/usr/txt{field_name}",
            f"wnd[0]/usr/ctxtRF02K-{field_name}",
            f"wnd[0]/usr/txtRF02K-{field_name}",
        ]
        # Supplier on BP screen
        if field_name.upper() in {"LIFNR", "SUPPLIER", "VENDOR"}:
            candidates.extend(
                [
                    "wnd[0]/usr/ctxtRF02K-LIFNR",
                    "wnd[0]/usr/ctxtBUS_JOEL_SEARCH-PARTNER_NUMBER",
                    "wnd[0]/usr/ctxtPARTNER",
                ]
            )
        for cid in candidates:
            try:
                el = self._session.FindById(cid)
                if self.show_mouse:
                    try:
                        from sapilot.connect.mouse import click_sap_component

                        click_sap_component(el)
                    except Exception:
                        pass
                el.Text = value
                self.log_action("fill_com", field=cid, value=value[:40])
                return True
            except Exception:
                continue
        return False

    def fill_fields_human(self, fields: list[tuple[float, float, str, bool]]) -> None:
        """
        Relative clicks — ONLY for non-tcode values.
        Rejects values that look like /nTCODE.
        """
        from sapilot.connect.mouse import click_window_point

        hwnd = self.focus_sap()
        if not hwnd:
            return
        for rx, ry, val, secret in fields:
            if _looks_like_tcode_command(val) and str(val).strip().upper().startswith("/"):
                self.log_action("blocked_tcode_mouse_type", value=val)
                continue
            click_window_point(hwnd, rx, ry)
            human_pause(0.1, 0.25)
            import win32com.client  # type: ignore

            win32com.client.Dispatch("WScript.Shell").SendKeys("^a")
            self.type_text(val, secret=secret)
            human_pause()
