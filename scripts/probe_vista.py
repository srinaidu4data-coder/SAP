"""Probe SAP Logon OpenConnection('Vista'). Credentials from vault only."""
from __future__ import annotations

import sys
import time

import win32com.client

from sapilot.env_load import load_dotenv
from pathlib import Path


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    from sapilot.security.vault import CredentialVault
    from sapilot.connect.logon import load_gui_logon_params

    params = load_gui_logon_params("vista", CredentialVault(passphrase="sapilot-local"))
    print("system:", params["system_description"], "user:", params["user"])

    sap = win32com.client.GetObject("SAPGUI")
    app = sap.GetScriptingEngine
    print("OpenConnection Vista...")
    app.OpenConnection(params["system_description"], True)
    for wait in range(1, 8):
        time.sleep(1)
        n = int(app.Children.Count)
        sessions = 0
        for i in range(n):
            sessions += int(app.Children(i).Children.Count)
        print(f"t+{wait}s connections={n} sessions={sessions}")
        if sessions:
            print("OK session available")
            return 0
    print(
        "FAILED: no scriptable sessions.\n"
        "SAP GUI trace typically says: 'Scripting not enabled by backend'.\n"
        "Ask Basis to set RZ11 sapgui/user_scripting = TRUE on Vista (S4H)."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
