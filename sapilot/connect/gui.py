"""SAP GUI Scripting via win32com — attach / session pool + MockGuiSession."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from sapilot.exceptions import ConnectionError as SapilotConnectionError
from sapilot.schemas import GuiElement, ScreenSnapshot

log = logging.getLogger(__name__)


class GuiSessionBase(ABC):
    @abstractmethod
    def start_transaction(self, tcode: str) -> None:
        ...

    @abstractmethod
    def find_by_id(self, element_id: str) -> Any:
        ...

    @abstractmethod
    def send_vkey(self, vkey: int) -> None:
        ...

    @abstractmethod
    def snapshot(self) -> ScreenSnapshot:
        ...

    @abstractmethod
    def status_bar_text(self) -> str:
        ...

    @abstractmethod
    def maximize(self) -> None:
        ...


class GuiSession(GuiSessionBase):
    """Live SAP GUI session (COM). Profile A: attach to existing Logon Pad connection."""

    def __init__(self, session: Any = None, connection_index: int = 0, session_index: int = 0):
        self._session = session
        self.connection_index = connection_index
        self.session_index = session_index

    @classmethod
    def attach(cls, connection_index: int = 0, session_index: int = 0) -> GuiSession:
        try:
            import win32com.client  # type: ignore
        except ImportError as e:
            raise SapilotConnectionError("pywin32 required for SAP GUI Scripting") from e
        try:
            SapGuiAuto = win32com.client.GetObject("SAPGUI")
            application = SapGuiAuto.GetScriptingEngine
        except Exception as e:
            raise SapilotConnectionError(
                f"SAP Logon scripting engine not available: {e}. "
                "Start SAP Logon Pad and enable scripting."
            ) from e
        try:
            n_conn = int(application.Children.Count)
        except Exception:
            n_conn = -1
        if n_conn == 0:
            raise SapilotConnectionError(
                "SAP Logon Pad is running but there is NO open system connection. "
                "Either log into a system manually, or run:\n"
                '  sapilot copilot login --system "Your Logon entry" --client 100 --user YOU'
            )
        try:
            connection = application.Children(connection_index)
            n_ses = int(connection.Children.Count)
            if n_ses == 0:
                raise SapilotConnectionError(
                    f"Connection {connection_index} has no sessions. Log into SAP first."
                )
            session = connection.Children(session_index)
            return cls(session=session, connection_index=connection_index, session_index=session_index)
        except SapilotConnectionError:
            raise
        except Exception as e:
            raise SapilotConnectionError(
                f"Cannot attach to SAP GUI (conn={connection_index}, ses={session_index}, "
                f"open_connections={n_conn}): {e}. "
                "Ensure a system is logged on, scripting enabled, notify-popups unchecked."
            ) from e

    @classmethod
    def list_open_sessions(cls) -> list[dict[str, Any]]:
        """Diagnose open connections/sessions on the running SAP Logon."""
        try:
            import win32com.client  # type: ignore
        except ImportError:
            return [{"error": "pywin32 not installed"}]
        try:
            SapGuiAuto = win32com.client.GetObject("SAPGUI")
            application = SapGuiAuto.GetScriptingEngine
        except Exception as e:
            return [{"error": f"SAPGUI not available: {e}"}]
        out: list[dict[str, Any]] = []
        try:
            for ci in range(int(application.Children.Count)):
                conn = application.Children(ci)
                for si in range(int(conn.Children.Count)):
                    ses = conn.Children(si)
                    info: dict[str, Any] = {"connection": ci, "session": si}
                    try:
                        info["tcode"] = str(ses.Info.Transaction)
                        info["user"] = str(ses.Info.User)
                        info["system"] = str(ses.Info.SystemName)
                        info["client"] = str(ses.Info.Client)
                    except Exception:
                        pass
                    out.append(info)
        except Exception as e:
            out.append({"error": str(e)})
        return out

    def start_transaction(self, tcode: str) -> None:
        self._session.StartTransaction(Transaction=tcode)

    def find_by_id(self, element_id: str) -> Any:
        return self._session.FindById(element_id)

    def send_vkey(self, vkey: int) -> None:
        self._session.FindById("wnd[0]").SendVKey(vkey)

    def maximize(self) -> None:
        try:
            self._session.FindById("wnd[0]").Maximize()
        except Exception:
            pass

    def status_bar_text(self) -> str:
        try:
            return str(self._session.FindById("wnd[0]/sbar").Text)
        except Exception:
            return ""

    def snapshot(self) -> ScreenSnapshot:
        from sapilot.observe.screen import serialize_session

        return serialize_session(self._session)


class MockGuiSession(GuiSessionBase):
    """Replays recorded screen snapshots for offline agent tests."""

    def __init__(
        self,
        screens: dict[str, ScreenSnapshot] | None = None,
        initial: str = "main",
    ):
        self.screens = screens or {}
        self.current_key = initial
        self.history: list[str] = []
        self.values: dict[str, str] = {}
        self.tcode = ""
        self._status = ""

    def load_screen(self, key: str, snap: ScreenSnapshot) -> None:
        self.screens[key] = snap

    def start_transaction(self, tcode: str) -> None:
        self.tcode = tcode.upper()
        self.history.append(f"tcode:{tcode}")
        # Prefer exact tcode key
        if self.tcode in self.screens:
            self.current_key = self.tcode
        self._status = ""

    def find_by_id(self, element_id: str) -> "_MockElement":
        snap = self.snapshot()
        el = snap.elements.find(element_id)
        if el is None:
            raise KeyError(f"Element not found: {element_id}")
        return _MockElement(self, el)

    def send_vkey(self, vkey: int) -> None:
        self.history.append(f"vkey:{vkey}")

    def maximize(self) -> None:
        pass

    def status_bar_text(self) -> str:
        return self._status

    def set_status(self, text: str) -> None:
        self._status = text

    def snapshot(self) -> ScreenSnapshot:
        if self.current_key not in self.screens:
            # empty shell
            return ScreenSnapshot(
                tcode=self.tcode,
                title="Mock SAP",
                elements=GuiElement(id="wnd[0]", type="GuiMainWindow", text="Mock"),
            )
        snap = self.screens[self.current_key].model_copy(deep=True)
        snap.tcode = self.tcode or snap.tcode
        snap.status_bar = self._status or snap.status_bar
        # Reflect typed field values so the agent sees its own writes
        if self.values:
            self._apply_values(snap.elements)
        return snap

    def _apply_values(self, el: GuiElement) -> None:
        if el.id in self.values:
            el.text = self.values[el.id]
        for child in el.children:
            self._apply_values(child)

    def press(self, element_id: str) -> None:
        self.history.append(f"press:{element_id}")
        # Allow scripted transitions via meta
        snap = self.snapshot()
        el = snap.elements.find(element_id)
        if el and el.extra.get("goto"):
            self.current_key = el.extra["goto"]


class _MockElement:
    def __init__(self, session: MockGuiSession, element: GuiElement):
        self._session = session
        self._element = element
        self.Id = element.id
        self.Text = element.text
        self.Name = element.name

    def SetFocus(self) -> None:
        self._session.history.append(f"focus:{self.Id}")

    def press(self) -> None:
        self._session.press(self.Id)

    def caretPosition(self, *_a: Any, **_k: Any) -> None:
        pass

    @property
    def text(self) -> str:
        return self._session.values.get(self.Id, self._element.text)

    @text.setter
    def text(self, value: str) -> None:
        self._session.values[self.Id] = value
        self._session.history.append(f"setText:{self.Id}={value}")
