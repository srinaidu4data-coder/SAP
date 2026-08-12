"""
High-level SAP GUI driver — human-like clicks, field fills, waits, table extract.
Used by Co-pilot for live Logon Pad sessions.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from sapilot.connect.gui import GuiSession, GuiSessionBase, MockGuiSession
from sapilot.exceptions import ConnectionError as SapilotConnectionError
from sapilot.observe.messages import parse_status_bar
from sapilot.observe.screen import flatten_elements
from sapilot.schemas import GuiElement, SapMessage, ScreenSnapshot

log = logging.getLogger(__name__)


class GuiDriver:
    """
    Co-pilot control surface over a GuiSession.
    Prefer element IDs from live snapshots; helpers can resolve by name/label.

    When SAPILOT_SHOW_MOUSE=1 (default), moves the real Windows cursor to each
    control before typing/clicking so demos are visible.
    """

    def __init__(
        self,
        session: GuiSessionBase,
        *,
        settle_seconds: float = 0.4,
        show_mouse: bool | None = None,
    ):
        self.session = session
        self.settle = settle_seconds
        self.history: list[dict[str, Any]] = []
        if show_mouse is None:
            from sapilot.connect.mouse import mouse_enabled

            self.show_mouse = mouse_enabled()
        else:
            self.show_mouse = show_mouse

    def _guard(self, op: str, **kw: Any) -> None:
        """Single policy choke-point — all writes go through WriteGuard."""
        from sapilot.policy.guard import authorize_write

        authorize_write(op, **kw)

    # --- navigation ---
    def start_transaction(self, tcode: str) -> ScreenSnapshot:
        tcode = tcode.strip().upper()
        self._guard("start_transaction", tcode=tcode, target=tcode, logical="navigate")
        self.session.start_transaction(tcode)
        self._pause()
        self._log("tcode", tcode=tcode)
        return self.snapshot()

    def send_enter(self) -> ScreenSnapshot:
        self._guard("send_vkey", target="vkey:0", logical="enter")
        self.session.send_vkey(0)
        self._pause()
        self._log("vkey", vkey=0)
        return self.snapshot()

    def send_f3(self) -> ScreenSnapshot:
        """Back."""
        self._guard("send_vkey", target="vkey:3", logical="back")
        self.session.send_vkey(3)
        self._pause()
        self._log("vkey", vkey=3)
        return self.snapshot()

    def send_f8(self) -> ScreenSnapshot:
        """Execute."""
        self._guard("send_vkey", target="vkey:8", logical="execute")
        self.session.send_vkey(8)
        self._pause()
        self._log("vkey", vkey=8)
        return self.snapshot()

    def maximize(self) -> None:
        self.session.maximize()

    # --- observation ---
    def snapshot(self) -> ScreenSnapshot:
        return self.session.snapshot()

    def status_bar(self) -> str:
        return self.session.status_bar_text()

    def last_message(self) -> SapMessage:
        return parse_status_bar(self.status_bar())

    def element_ids(self) -> set[str]:
        return self.snapshot().element_ids()

    def flat_elements(self) -> list[dict[str, str]]:
        snap = self.snapshot()
        return flatten_elements(snap.elements)

    def find_id_by_name(self, name: str, *, type_hint: str | None = None) -> str | None:
        """Resolve SAP element id from Name or visible Text (exact, case-insensitive)."""
        name_l = name.lower().strip()
        for el in self.flat_elements():
            if type_hint and type_hint.lower() not in el.get("type", "").lower():
                continue
            if el.get("name", "").lower() == name_l or el.get("text", "").lower() == name_l:
                return el["id"]
        # partial
        for el in self.flat_elements():
            if name_l in (el.get("name") or "").lower() or name_l in (el.get("text") or "").lower():
                if type_hint and type_hint.lower() not in el.get("type", "").lower():
                    continue
                return el["id"]
        return None

    def require_id(self, target: str) -> str:
        """target is either an exact id or a name to resolve."""
        ids = self.element_ids()
        if target in ids:
            return target
        resolved = self.find_id_by_name(target)
        if resolved and resolved in ids:
            return resolved
        raise KeyError(
            f"Control '{target}' not on screen. Available sample: {sorted(list(ids))[:15]}"
        )

    def _mouse_to_com(self, com_el: Any) -> bool:
        """Visibly move cursor onto a live SAP COM control and click."""
        if not self.show_mouse or isinstance(self.session, MockGuiSession):
            return False
        try:
            from sapilot.connect.mouse import click_sap_component

            return click_sap_component(com_el)
        except Exception as e:
            log.debug("mouse point failed: %s", e)
            return False

    # --- grounded actions ---
    def set_text(self, target: str, value: str) -> ScreenSnapshot:
        eid = self.require_id(target)
        self._guard("set_text", target=eid, value=str(value), logical="set_text")
        el = self.session.find_by_id(eid)
        # Visible mouse: click the field first so you see focus move
        mouse_hit = self._mouse_to_com(el)
        if hasattr(el, "text"):
            el.text = value
        else:
            el.Text = value
        try:
            el.caretPosition = len(str(value))
        except Exception:
            pass
        self._log("setText", target=eid, value=value, mouse=mouse_hit)
        self._pause(0.15)
        return self.snapshot()

    def press(self, target: str) -> ScreenSnapshot:
        eid = self.require_id(target)
        self._guard("press", target=eid, logical="press")
        el = self.session.find_by_id(eid)
        mouse_hit = self._mouse_to_com(el)
        if isinstance(self.session, MockGuiSession):
            self.session.press(eid)
        else:
            # Live COM — mouse click may already have activated; still Press for reliability
            try:
                if not mouse_hit:
                    el.Press()
                else:
                    try:
                        el.Press()
                    except Exception:
                        pass  # physical click already delivered
            except Exception:
                if hasattr(el, "press"):
                    el.press()
                else:
                    raise
        self._log("press", target=eid, mouse=mouse_hit)
        self._pause()
        return self.snapshot()

    def select(self, target: str) -> ScreenSnapshot:
        eid = self.require_id(target)
        self._guard("select", target=eid, logical="select")
        el = self.session.find_by_id(eid)
        mouse_hit = self._mouse_to_com(el)
        if isinstance(self.session, MockGuiSession):
            self.session.press(eid)
        else:
            try:
                el.Select()
            except Exception:
                try:
                    el.Press()
                except Exception:
                    el.Selected = True  # type: ignore[attr-defined]
        self._log("select", target=eid, mouse=mouse_hit)
        self._pause()
        return self.snapshot()

    def set_ok_code(self, tcode_or_command: str) -> ScreenSnapshot:
        """Type in command field and Enter (alternate to StartTransaction)."""
        candidates = [
            "wnd[0]/tbar[0]/okcd",
            "okcd",
        ]
        eid = None
        for c in candidates:
            try:
                eid = self.require_id(c)
                break
            except KeyError:
                continue
        if not eid:
            # fall back to StartTransaction for pure tcodes
            return self.start_transaction(tcode_or_command)
        self.set_text(eid, tcode_or_command)
        return self.send_enter()

    # --- table extraction (GUI channel) ---
    def extract_table_control(self, table_id: str | None = None, max_rows: int = 200) -> list[dict[str, str]]:
        """
        Extract GuiTableControl rows. If table_id omitted, first table-like node is used.
        """
        if isinstance(self.session, MockGuiSession):
            return self._extract_table_from_snapshot(table_id, max_rows)

        session = getattr(self.session, "_session", None)
        if session is None:
            return self._extract_table_from_snapshot(table_id, max_rows)

        tid = table_id
        if not tid:
            for el in self.flat_elements():
                if "tbl" in el.get("id", "").lower() or "table" in el.get("type", "").lower():
                    tid = el["id"]
                    break
        if not tid:
            return []

        try:
            tbl = session.FindById(tid)
            rows_out: list[dict[str, str]] = []
            # Prefer ColumnOrder + GetCellValue when available (ALV shell)
            try:
                row_count = int(tbl.RowCount)
                col_count = int(tbl.ColumnCount)
                col_names = []
                for c in range(min(col_count, 40)):
                    try:
                        col_names.append(str(tbl.ColumnOrder(c)))
                    except Exception:
                        col_names.append(f"COL{c}")
                for r in range(min(row_count, max_rows)):
                    row = {}
                    for c, name in enumerate(col_names):
                        try:
                            row[name] = str(tbl.GetCellValue(r, name))
                        except Exception:
                            try:
                                row[name] = str(tbl.GetCellValue(r, c))
                            except Exception:
                                row[name] = ""
                    rows_out.append(row)
                self._log("extract_table", table_id=tid, rows=len(rows_out))
                return rows_out
            except Exception:
                pass

            # Classic table control: rows collection
            try:
                row_count = int(tbl.RowCount)
                for r in range(min(row_count, max_rows)):
                    row: dict[str, str] = {"_row": str(r)}
                    try:
                        cols = tbl.Columns.Count
                        for c in range(min(int(cols), 40)):
                            try:
                                cell = tbl.GetCell(r, c)
                                name = str(getattr(cell, "Name", f"C{c}"))
                                row[name] = str(getattr(cell, "Text", ""))
                            except Exception:
                                pass
                    except Exception:
                        pass
                    rows_out.append(row)
                self._log("extract_table", table_id=tid, rows=len(rows_out))
                return rows_out
            except Exception as e:
                log.warning("Table extract failed for %s: %s", tid, e)
                return self._extract_table_from_snapshot(tid, max_rows)
        except Exception as e:
            log.warning("Find table %s failed: %s", tid, e)
            return []

    def _extract_table_from_snapshot(
        self, table_id: str | None, max_rows: int
    ) -> list[dict[str, str]]:
        snap = self.snapshot()
        rows: list[dict[str, str]] = []

        def walk(el: GuiElement) -> None:
            if table_id and el.id != table_id:
                for c in el.children:
                    walk(c)
                return
            if el.type in {"GuiTableControl", "GuiShell"} or (table_id and el.id == table_id):
                for i, child in enumerate(el.children[:max_rows]):
                    rows.append({"id": child.id, "text": child.text, "name": child.name, "_i": str(i)})
            for c in el.children:
                walk(c)

        walk(snap.elements)
        return rows

    # --- scripting helpers ---
    def wait_for_element(self, target: str, timeout: float = 15.0) -> str:
        deadline = time.time() + timeout
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                return self.require_id(target)
            except Exception as e:
                last_err = e
                time.sleep(0.35)
        raise TimeoutError(f"Element '{target}' not found within {timeout}s: {last_err}")

    def wait_status_not_busy(self, timeout: float = 60.0) -> str:
        """Poll status bar until it no longer looks like 'running' (best effort)."""
        deadline = time.time() + timeout
        text = self.status_bar()
        busy = re.compile(r"running|please wait|processing", re.I)
        while time.time() < deadline:
            text = self.status_bar()
            if not busy.search(text or ""):
                return text
            time.sleep(0.5)
        return text

    def _pause(self, seconds: float | None = None) -> None:
        time.sleep(self.settle if seconds is None else seconds)

    def _log(self, action: str, **kwargs: Any) -> None:
        self.history.append({"action": action, **kwargs})


def open_live_session(
    *,
    attach: bool = False,
    connection_index: int = 0,
    session_index: int = 0,
    system_description: str | None = None,
    client: str | None = None,
    user: str | None = None,
    password: str | None = None,
    language: str = "EN",
) -> GuiDriver:
    """
    Attach to an already-open SAP GUI session, or open via Logon Pad description.
    """
    if attach or not system_description:
        try:
            gui = GuiSession.attach(connection_index, session_index)
            gui.maximize()
            return GuiDriver(gui)
        except Exception as e:
            if attach:
                raise SapilotConnectionError(str(e)) from e
            raise

    from sapilot.connect.logon import gui_logon

    if not all([system_description, client, user, password]):
        raise SapilotConnectionError(
            "Logon requires system_description, client, user, password "
            "(or use --attach to an existing session)"
        )
    gui = gui_logon(
        system_description,  # type: ignore[arg-type]
        client,  # type: ignore[arg-type]
        user,  # type: ignore[arg-type]
        password,  # type: ignore[arg-type]
        language,
    )
    gui.maximize()
    return GuiDriver(gui)
