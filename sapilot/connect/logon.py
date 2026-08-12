"""
SAP Logon Pad login — bug-resistant credential entry.

SAP login screen field order (left to right / tab order):
  1) Client   (txtRSYST-MANDT)   e.g. 100
  2) User     (txtRSYST-BNAME)   e.g. SV3_000349
  3) Password (pwdRSYST-BCODE)
  4) Language (txtRSYST-LANGU)   e.g. EN

IMPORTANT: When the login window opens, keyboard focus is almost always on
**User**, not Client. A naive "type client first" SendKeys sequence puts
"100" into the username field. This module:
  - Prefer COM Scripting field IDs (never depends on focus)
  - Keyboard fallback: Shift+TAB to Client, then Client → User → Password → Enter
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from sapilot.exceptions import ConnectionError as SapilotConnectionError
from sapilot.exceptions import CredentialsEnteredNoScripting
from sapilot.security.vault import CredentialVault

log = logging.getLogger(__name__)

_SAPLOGON_CANDIDATES = [
    r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe",
    r"C:\Program Files\SAP\FrontEnd\SAPgui\saplogon.exe",
    r"C:\Program Files (x86)\SAP\FrontEnd\SapGui\saplogon.exe",
]

# Known login field IDs (classic dynpro)
_FIELD_CLIENT = [
    "wnd[0]/usr/txtRSYST-MANDT",
    "wnd[0]/usr/txtRSYST-MANDT1",
]
_FIELD_USER = [
    "wnd[0]/usr/txtRSYST-BNAME",
    "wnd[0]/usr/txtRSYST-BNAME1",
]
_FIELD_PASSWORD = [
    "wnd[0]/usr/pwdRSYST-BCODE",
    "wnd[0]/usr/pwdRSYST-BCODE1",
]
_FIELD_LANGUAGE = [
    "wnd[0]/usr/txtRSYST-LANGU",
    "wnd[0]/usr/txtRSYST-LANGU1",
]


def build_rfc_params(
    ashost: str,
    sysnr: str,
    client: str,
    user: str,
    passwd: str,
    lang: str = "EN",
    **extra: Any,
) -> dict[str, Any]:
    params = {
        "ashost": ashost,
        "sysnr": sysnr,
        "client": client,
        "user": user,
        "passwd": passwd,
        "lang": lang,
    }
    params.update(extra)
    return params


def load_connection(name: str, vault: CredentialVault | None = None) -> dict[str, Any]:
    v = vault or CredentialVault()
    creds = v.get(name)
    if not creds:
        raise SapilotConnectionError(
            f"No credentials for connection '{name}'. Run: sapilot vault set {name}"
        )
    return build_rfc_params(
        ashost=creds.get("ashost", ""),
        sysnr=creds.get("sysnr", "00"),
        client=creds.get("client", ""),
        user=creds.get("user", ""),
        passwd=creds.get("passwd", creds.get("password", "")),
        lang=creds.get("lang", "EN"),
        **{
            k: v
            for k, v in creds.items()
            if k
            not in {
                "ashost",
                "sysnr",
                "client",
                "user",
                "passwd",
                "password",
                "lang",
                "system",
                "description",
            }
        },
    )


def load_gui_logon_params(name: str, vault: CredentialVault | None = None) -> dict[str, str]:
    v = vault or CredentialVault()
    creds = v.get(name)
    if not creds:
        raise SapilotConnectionError(
            f"No credentials for connection '{name}'. Run: sapilot vault set {name}"
        )
    system = (
        creds.get("system")
        or creds.get("description")
        or creds.get("system_description")
        or name
    )
    return {
        "system_description": str(system),
        "client": str(creds.get("client", "100")),
        "user": str(creds.get("user", "")),
        "password": str(creds.get("passwd") or creds.get("password") or ""),
        "language": str(creds.get("lang", "EN")),
    }


def find_saplogon_exe() -> str | None:
    env = os.environ.get("SAPLOGON_PATH")
    if env and Path(env).exists():
        return env
    for p in _SAPLOGON_CANDIDATES:
        if Path(p).exists():
            return p
    from shutil import which

    return which("saplogon.exe")


def ensure_saplogon_running(wait: float = 4.0) -> None:
    try:
        import win32com.client  # type: ignore

        win32com.client.GetObject("SAPGUI")
        return
    except Exception:
        pass

    exe = find_saplogon_exe()
    if not exe:
        raise SapilotConnectionError(
            "SAP Logon Pad not found. Install SAP GUI for Windows or set SAPLOGON_PATH."
        )
    log.info("Starting SAP Logon: %s", exe)
    subprocess.Popen([exe], shell=False)  # noqa: S603
    time.sleep(wait)


def _escape_sendkeys(text: str) -> str:
    out: list[str] = []
    for ch in text:
        if ch in "+^%~(){}[]":
            out.append("{" + ch + "}")
        else:
            out.append(ch)
    return "".join(out)


def _list_sap_session_hwnds() -> list[int]:
    try:
        import win32gui  # type: ignore
    except ImportError:
        return []

    hwnds: list[int] = []

    def cb(hwnd: int, _: Any) -> None:
        if not win32gui.IsWindowVisible(hwnd):
            return
        cls = win32gui.GetClassName(hwnd)
        if cls == "SAP_FRONTEND_SESSION":
            hwnds.append(hwnd)

    win32gui.EnumWindows(cb, None)
    return hwnds


def _activate_hwnd(hwnd: int) -> bool:
    import win32con  # type: ignore
    import win32gui  # type: ignore

    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)
        return True
    except Exception as e:
        log.warning("SetForegroundWindow failed: %s", e)
        try:
            import win32com.client  # type: ignore

            title = win32gui.GetWindowText(hwnd) or "SAP"
            win32com.client.Dispatch("WScript.Shell").AppActivate(title)
            time.sleep(0.5)
            return True
        except Exception:
            return False


def _set_text_com(session: Any, candidates: list[str], value: str, label: str) -> str:
    last: Exception | None = None
    for fid in candidates:
        try:
            el = session.FindById(fid)
            el.Text = value
            log.info("Set %s via %s = %r", label, fid, value if label != "password" else "***")
            return fid
        except Exception as e:
            last = e
    raise SapilotConnectionError(f"Cannot set {label} field: {last}")


def fill_login_via_com(
    session: Any,
    client: str,
    user: str,
    password: str,
    language: str = "EN",
) -> dict[str, str]:
    """
    Fill login fields by SAP element ID — correct mapping always:
      Client field ← client (e.g. 100)
      User field   ← username
      Password     ← password
    """
    if not client or not user or not password:
        raise SapilotConnectionError("client, user, and password are all required")

    used = {
        "client": _set_text_com(session, _FIELD_CLIENT, client.strip(), "client"),
        "user": _set_text_com(session, _FIELD_USER, user.strip(), "user"),
        "password": _set_text_com(session, _FIELD_PASSWORD, password, "password"),
    }
    try:
        used["language"] = _set_text_com(
            session, _FIELD_LANGUAGE, (language or "EN").strip(), "language"
        )
    except Exception:
        log.debug("Language field not set (optional)")

    # Verify COM values (password not readable usually)
    try:
        got_client = str(session.FindById(used["client"]).Text).strip()
        got_user = str(session.FindById(used["user"]).Text).strip()
        if got_client != client.strip():
            raise SapilotConnectionError(
                f"Client field verification failed: expected {client!r}, got {got_client!r}"
            )
        if got_user.upper() != user.strip().upper():
            raise SapilotConnectionError(
                f"User field verification failed: expected {user!r}, got {got_user!r}"
            )
        log.info("Verified COM login fields: client=%s user=%s", got_client, got_user)
    except SapilotConnectionError:
        raise
    except Exception as e:
        log.warning("Could not verify COM fields: %s", e)

    session.FindById("wnd[0]").SendVKey(0)
    time.sleep(2.0)
    _dismiss_popups_com(session)
    return used


def _dismiss_popups_com(session: Any) -> None:
    for _ in range(5):
        try:
            session.FindById("wnd[1]/usr/radMULTI_LOGON_OPT2").Select()
            session.FindById("wnd[1]/tbar[0]/btn[0]").Press()
            time.sleep(0.4)
            continue
        except Exception:
            pass
        try:
            session.FindById("wnd[1]/tbar[0]/btn[0]").Press()
            time.sleep(0.4)
        except Exception:
            break


def fill_login_via_keyboard(
    client: str,
    user: str,
    password: str,
    language: str = "EN",
    *,
    hwnd: int | None = None,
) -> None:
    """
    Keyboard + visible mouse fallback when COM scripting has no session.

    1) Move mouse and click Client / User / Password field positions
    2) Type values (Client is never put in the username field)
    """
    import win32com.client  # type: ignore

    client = (client or "").strip()
    user = (user or "").strip()
    if not client or not user or not password:
        raise SapilotConnectionError("client, user, and password are all required")

    if hwnd is None:
        hwnds = _list_sap_session_hwnds()
        if not hwnds:
            raise SapilotConnectionError(
                "No SAP login window found. Open the system from SAP Logon first."
            )
        hwnd = hwnds[-1]

    if not _activate_hwnd(hwnd):
        raise SapilotConnectionError("Could not focus SAP login window")

    shell = win32com.client.Dispatch("WScript.Shell")
    time.sleep(0.25)

    log.info(
        "Keyboard+mouse login: Client=%r → User=%r → Password=***",
        client,
        user,
    )

    # Approximate classic SAP logon field centers (relative to window).
    # Mouse moves visibly to each field before typing.
    try:
        from sapilot.connect.mouse import click_window_point, mouse_enabled

        if mouse_enabled():
            # Client
            click_window_point(hwnd, 0.48, 0.42)
            time.sleep(0.12)
            shell.SendKeys("^a")
            shell.SendKeys(_escape_sendkeys(client))
            time.sleep(0.15)
            # User
            click_window_point(hwnd, 0.48, 0.48)
            time.sleep(0.12)
            shell.SendKeys("^a")
            shell.SendKeys(_escape_sendkeys(user))
            time.sleep(0.15)
            # Password
            click_window_point(hwnd, 0.48, 0.54)
            time.sleep(0.12)
            shell.SendKeys("^a")
            shell.SendKeys(_escape_sendkeys(password))
            time.sleep(0.15)
            shell.SendKeys("{ENTER}")
            time.sleep(2.5)
            return
    except Exception as e:
        log.warning("Mouse login path failed (%s); Shift+TAB keyboard only", e)

    # Fallback without mouse: Shift+TAB from default User focus → Client
    shell.SendKeys("+{TAB}")
    time.sleep(0.2)
    shell.SendKeys("^a")
    shell.SendKeys(_escape_sendkeys(client))
    time.sleep(0.12)
    shell.SendKeys("{TAB}")
    time.sleep(0.12)
    shell.SendKeys("^a")
    shell.SendKeys(_escape_sendkeys(user))
    time.sleep(0.12)
    shell.SendKeys("{TAB}")
    time.sleep(0.12)
    shell.SendKeys("^a")
    shell.SendKeys(_escape_sendkeys(password))
    time.sleep(0.12)
    shell.SendKeys("{ENTER}")
    time.sleep(2.5)


def _wait_for_scriptable_session(application: Any, connection: Any, wait_seconds: float) -> Any:
    deadline = time.time() + max(wait_seconds, 2.0)
    while time.time() < deadline:
        try:
            for ci in range(int(application.Children.Count)):
                conn = application.Children(ci)
                if int(conn.Children.Count) > 0:
                    return conn.Children(0)
            if connection is not None and int(connection.Children.Count) > 0:
                return connection.Children(0)
        except Exception:
            pass
        time.sleep(0.35)
    return None


def gui_logon(
    system_description: str,
    client: str,
    user: str,
    password: str,
    language: str = "EN",
    *,
    wait_seconds: float = 15.0,
) -> Any:
    """
    Open SAP Logon entry and fill:
      Client = client (e.g. 100)
      User   = user
      Password = password
    Never puts client into the username field.
    """
    client = (client or "").strip()
    user = (user or "").strip()
    password = password or ""
    language = (language or "EN").strip() or "EN"

    if not client:
        raise SapilotConnectionError("Client is required (e.g. 100) — not the username")
    if not user:
        raise SapilotConnectionError("Username is required")
    if not password:
        raise SapilotConnectionError("Password is required")
    if client == user:
        raise SapilotConnectionError(
            f"Client and username are both {client!r} — that is almost certainly wrong. "
            "Client is the 3-digit mandt (e.g. 100); username is the SAP user id."
        )

    try:
        import win32com.client  # type: ignore
    except ImportError as e:
        raise SapilotConnectionError("pywin32 required: pip install pywin32") from e

    ensure_saplogon_running()

    try:
        SapGuiAuto = win32com.client.GetObject("SAPGUI")
    except Exception as e:
        raise SapilotConnectionError(
            f"SAP GUI not available: {e}. Start SAP Logon Pad."
        ) from e

    application = SapGuiAuto.GetScriptingEngine
    hwnds_before = set(_list_sap_session_hwnds())

    log.info(
        "OpenConnection %r then login client=%r user=%r",
        system_description,
        client,
        user,
    )
    try:
        connection = application.OpenConnection(system_description, True)
    except Exception as e:
        raise SapilotConnectionError(
            f"OpenConnection({system_description!r}) failed: {e}. "
            "Name must match SAP Logon Pad exactly (e.g. Vista)."
        ) from e

    time.sleep(1.2)
    session = _wait_for_scriptable_session(application, connection, min(wait_seconds, 6.0))

    method = None
    if session is not None:
        try:
            fill_login_via_com(session, client, user, password, language)
            method = "com"
        except Exception as e:
            log.warning("COM field fill failed (%s); using keyboard with Client-first focus", e)
            session = None

    if method is None:
        hwnd = None
        deadline = time.time() + 12
        while time.time() < deadline:
            hwnds = _list_sap_session_hwnds()
            new = [h for h in hwnds if h not in hwnds_before]
            if new:
                hwnd = new[-1]
                break
            if hwnds:
                hwnd = hwnds[-1]
            time.sleep(0.35)
        fill_login_via_keyboard(client, user, password, language, hwnd=hwnd)
        method = "keyboard"
        session = _wait_for_scriptable_session(application, connection, 5.0)

    from sapilot.connect.gui import GuiSession

    if session is not None and method == "com":
        return GuiSession(session=session)

    if session is not None:
        # Keyboard login then COM became available
        return GuiSession(session=session)

    raise CredentialsEnteredNoScripting(
        f"Login fields filled correctly: Client={client!r}, User={user!r}, Password=*** "
        f"(method={method}, system={system_description!r}). "
        "Confirm on the SAP window. Full automation after login needs "
        "sapgui/user_scripting=TRUE on the server.",
        method=method or "keyboard",
    )


def gui_logon_from_vault(connection_name: str, vault: CredentialVault | None = None) -> Any:
    params = load_gui_logon_params(connection_name, vault)
    return gui_logon(
        params["system_description"],
        params["client"],
        params["user"],
        params["password"],
        params["language"],
    )
