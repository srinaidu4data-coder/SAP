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
        from sapilot.connect.hwnd_input import bind_session

        bind_session().type_text(text, secret=secret)
        self.log_action("type", text="***" if secret else text[:40])
        human_pause(0.08, 0.2)

    def press_enter(self) -> None:
        from sapilot.connect.hwnd_input import bind_session

        bind_session().send_key("ENTER")
        self.log_action("enter")
        human_pause()

    def press_escape(self) -> None:
        from sapilot.connect.hwnd_input import bind_session

        bind_session().send_key("ESC")
        self.log_action("escape")
        human_pause(0.1, 0.25)

    def focus_sap(self) -> int | None:
        try:
            from sapilot.connect.hwnd_input import bind_session
            from sapilot.connect.mouse import focus_window

            sess = bind_session()
            focus_window(sess.hwnd)
            self.log_action("focus_sap", hwnd=sess.hwnd, pid=sess.pid, title=sess.title)
            return sess.hwnd
        except Exception as e:
            self.log_action("focus_sap_fail", error=str(e)[:200])
            return None

    def start_transaction(self, tcode: str) -> bool:
        """
        Navigate to a tcode the CORRECT way.

        Priority:
          1) COM StartTransaction (never touches Supplier/Vendor fields)
          2) COM ok-code toolbar field only (wnd[0]/tbar[0]/okcd)
          3) hwnd command field (identified control, not a window fraction)
          4) Fail closed — never type a tcode into a data field
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

        # Scripting off: type /nTCODE into the real command field (hwnd+pid), never
        # a window-fraction click. Fail closed if the okcd control is not found.
        try:
            from sapilot.connect.hwnd_input import bind_session

            sess = bind_session()
            sess.start_transaction(tcode)
            self.log_action("start_transaction_hwnd", tcode=tcode, hwnd=sess.hwnd, pid=sess.pid)
            return True
        except Exception as e:
            self.log_action(
                "start_transaction_hwnd_fail",
                tcode=tcode,
                reason=str(e)[:200],
            )
            return False

    def type_okcode(self, tcode: str) -> None:
        """Backward-compatible name — always uses safe start_transaction."""
        ok = self.start_transaction(tcode)
        if not ok:
            log.warning(
                "Could not navigate to %s safely. Need a focused SAP_FRONTEND_SESSION "
                "and an identifiable command field (or enable sapgui/user_scripting).",
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
            from sapilot.connect.hwnd_input import bind_session

            bind_session(hwnd=hwnd).clear_field()
            self.type_text(val, secret=secret)
            human_pause()
