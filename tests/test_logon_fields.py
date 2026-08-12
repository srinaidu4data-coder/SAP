"""Unit tests for login field mapping (no live SAP required)."""

from __future__ import annotations

import pytest

from sapilot.connect.logon import _escape_sendkeys
from sapilot.exceptions import ConnectionError as SapilotConnectionError


def test_escape_sendkeys_password_specials():
    assert _escape_sendkeys("ab+c") == "ab{+}c"
    assert _escape_sendkeys("Srsoft2026") == "Srsoft2026"


def test_gui_logon_rejects_client_equals_user():
    from sapilot.connect import logon as logon_mod

    with pytest.raises(SapilotConnectionError, match="Client and username"):
        logon_mod.gui_logon("Vista", "100", "100", "secret")


def test_gui_logon_requires_client():
    from sapilot.connect import logon as logon_mod

    with pytest.raises(SapilotConnectionError, match="Client is required"):
        logon_mod.gui_logon("Vista", "", "SV3_000349", "secret")
