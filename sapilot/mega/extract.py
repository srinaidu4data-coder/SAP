"""
Online multi-table extraction for Mega Co-pilot.

Channels (in order):
  1. RFC_READ_TABLE (if pyrfc + SDK available)
  2. Live SAP GUI session via SE16N scripting
  3. Mock only if explicitly allowed (lab)

All production Mega paths prefer live data.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sapilot.connect.driver import GuiDriver
from sapilot.connect.rfc import MockRfcClient, RfcClient, RfcClientBase
from sapilot.know.gather import ScenarioDataGatherer, DataPack, load_packs

log = logging.getLogger(__name__)


class OnlineExtractor:
    def __init__(
        self,
        rfc: RfcClientBase | None = None,
        driver: GuiDriver | None = None,
        *,
        allow_mock: bool = False,
    ):
        self.rfc = rfc
        self.driver = driver
        self.allow_mock = allow_mock
        self.mode = "none"
        self._ensure_channel()

    def _ensure_channel(self) -> None:
        if self.rfc is not None and not isinstance(self.rfc, MockRfcClient):
            self.mode = "rfc"
            return
        if self.rfc is not None and isinstance(self.rfc, MockRfcClient) and self.allow_mock:
            self.mode = "mock"
            return
        if self.driver is not None and not isinstance(
            getattr(self.driver.session, "__class__", type), type
        ):
            pass
        if self.driver is not None:
            from sapilot.connect.gui import MockGuiSession

            if not isinstance(self.driver.session, MockGuiSession):
                self.mode = "gui_se16n"
                if self.rfc is None:
                    self.rfc = _GuiBackedRfc(self.driver)
                return
        if self.allow_mock:
            from sapilot.demo_data_ptp import seed_ptp_tables

            self.rfc = MockRfcClient()
            seed_ptp_tables(self.rfc)
            self.mode = "mock"
            return
        raise RuntimeError(
            "No online data channel. Need live RFC (pyrfc) or live SAP GUI session with scripting."
        )

    def read_table(
        self,
        table: str,
        fields: list[str] | None = None,
        options: list[str] | None = None,
        rowcount: int = 100,
    ) -> dict[str, Any]:
        assert self.rfc is not None
        rows = self.rfc.read_table(table, fields=fields, options=options, rowcount=rowcount)
        return {
            "channel": self.mode,
            "table": table,
            "options": options or [],
            "count": len(rows),
            "rows": rows,
        }

    def gather_pack(self, pack_id: str, params: dict[str, Any] | None = None) -> DataPack:
        assert self.rfc is not None
        return ScenarioDataGatherer(self.rfc).gather(pack_id, params)

    def extract_for_scenario(
        self, scenario_id: str, params: dict[str, Any] | None = None
    ) -> DataPack:
        packs = load_packs()
        if scenario_id in packs:
            return self.gather_pack(scenario_id, params)
        # fallback full chain for unknown
        if "ptp" in scenario_id or scenario_id.startswith("f110"):
            return self.gather_pack("ptp_full_chain", params)
        raise KeyError(f"No data pack for scenario {scenario_id}")


class _GuiBackedRfc(RfcClientBase):
    """
    Emulates RFC_READ_TABLE by driving SE16N on a live GuiDriver.
    Online when COM scripting works; slower but real system data.
    """

    def __init__(self, driver: GuiDriver):
        self.driver = driver
        self.calls: list = []

    def call(self, func: str, **params: Any) -> dict[str, Any]:
        if func == "RFC_PING":
            return {}
        if func in ("RFC_READ_TABLE", "/SAPDS/RFC_READ_TABLE"):
            table = params.get("QUERY_TABLE", "")
            opts = params.get("OPTIONS") or []
            options = [o.get("TEXT", "") if isinstance(o, dict) else str(o) for o in opts]
            rowcount = int(params.get("ROWCOUNT") or 50)
            rows = self._se16n(table, options, rowcount)
            fields = list(rows[0].keys()) if rows else []
            delim = params.get("DELIMITER") or "|"
            return {
                "FIELDS": [{"FIELDNAME": f} for f in fields],
                "DATA": [{"WA": delim.join(str(r.get(f, "")) for f in fields)} for r in rows],
            }
        return {}

    def read_table(
        self,
        table: str,
        fields: list[str] | None = None,
        options: list[str] | None = None,
        rowcount: int = 0,
        delimiter: str = "|",
    ) -> list[dict[str, str]]:
        return self._se16n(table, options or [], rowcount or 50)

    def _se16n(self, table: str, options: list[str], rowcount: int) -> list[dict[str, str]]:
        d = self.driver
        log.info("SE16N online extract table=%s options=%s", table, options)
        d.start_transaction("SE16N")
        time.sleep(0.4)
        # Table name field
        for name in ("GD-TAB", "I_TAB", "TABNAME", "GS_SE16N-TAB"):
            try:
                d.set_text(name, table.upper())
                break
            except KeyError:
                continue
        # Best-effort: number of hits
        for name in ("GD-MAX_LINES", "I_MAXLINES", "MAX_SEL"):
            try:
                d.set_text(name, str(min(rowcount or 50, 200)))
                break
            except KeyError:
                continue
        try:
            d.send_f8()
        except Exception:
            d.send_enter()
        time.sleep(0.8)
        grid = d.extract_table_control(max_rows=rowcount or 50)
        # Normalize grid cells → row dicts
        if not grid:
            # degraded: return empty with note via single row
            return []
        # If already dict rows with field names
        if grid and all(isinstance(r, dict) for r in grid):
            # filter options client-side lightly
            rows = grid
            for opt in options:
                rows = _filter_opt(rows, opt)
            return rows[: rowcount or 50]
        return grid[: rowcount or 50]


def _filter_opt(rows: list[dict[str, str]], text: str) -> list[dict[str, str]]:
    import re

    text = text.strip()
    text = re.sub(r"^(AND|OR)\s+", "", text, flags=re.I)
    m = re.match(r"(\w+)\s*(?:=|EQ)\s*'([^']*)'", text, re.I)
    if not m:
        return rows
    field, value = m.group(1).upper(), m.group(2)
    return [r for r in rows if str(r.get(field, r.get(field.lower(), ""))) == value]


def connect_live_rfc(connection_name: str = "vista") -> RfcClient | None:
    try:
        import os

        from sapilot.connect.logon import load_connection
        from sapilot.security.vault import CredentialVault

        vault = CredentialVault(passphrase=os.environ.get("SAPILOT_VAULT_PASSPHRASE", "sapilot-local"))
        params = load_connection(connection_name, vault)
        if not params.get("ashost"):
            return None
        rfc = RfcClient(params)
        rfc.connect()
        return rfc
    except Exception as e:
        log.warning("Live RFC unavailable: %s", e)
        return None
