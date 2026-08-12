"""
Dual-channel data extraction for Co-pilot.
KNOWLEDGE channel (RFC) preferred; GUI table scrape as fallback (degraded).
"""

from __future__ import annotations

import logging
from typing import Any

from sapilot.connect.driver import GuiDriver
from sapilot.connect.rfc import RfcClientBase
from sapilot.know.tables import KnowledgeTables
from sapilot.observe.messages import MessageResolver

log = logging.getLogger(__name__)


class DataExtractor:
    def __init__(
        self,
        rfc: RfcClientBase | None = None,
        driver: GuiDriver | None = None,
    ):
        self.rfc = rfc
        self.driver = driver
        self.tables = KnowledgeTables(rfc) if rfc else None
        self.messages = MessageResolver(rfc) if rfc else None
        self.degraded = False

    def read_table(
        self,
        table: str,
        fields: list[str] | None = None,
        options: list[str] | None = None,
        rowcount: int = 100,
    ) -> dict[str, Any]:
        if self.rfc is not None:
            rows = self.rfc.read_table(
                table, fields=fields, options=options, rowcount=rowcount
            )
            return {"channel": "rfc", "table": table, "rows": rows, "count": len(rows)}

        # Degraded: open SE16N via GUI if driver present
        if self.driver is not None:
            self.degraded = True
            log.warning("RFC unavailable — SE16N GUI fallback for %s", table)
            return self._se16n_read(table, rowcount=rowcount)

        return {
            "channel": "none",
            "table": table,
            "rows": [],
            "count": 0,
            "error": "No RFC or GUI available for table read",
        }

    def fbzp_snapshot(self, bukrs: str, zlsch: str, land1: str = "US") -> dict[str, Any]:
        if self.tables is None:
            return {"error": "RFC knowledge channel required for FBZP snapshot"}
        return self.tables.fbzp_chain_snapshot(bukrs, zlsch, land1)

    def vendor_pack(self, lifnr: str, bukrs: str) -> dict[str, Any]:
        if self.tables is None:
            return {"error": "RFC required"}
        return {
            "LFA1": self.tables.lfa1(lifnr),
            "LFB1": self.tables.lfb1(lifnr, bukrs),
            "LFBK": self.tables.lfbk(lifnr),
            "BSIK": self.tables.bsik(bukrs, lifnr=lifnr),
        }

    def payment_run_status(self, laufd: str, laufi: str) -> dict[str, Any]:
        if self.tables is None:
            return {"error": "RFC required"}
        return {
            "REGUV": self.tables.reguv(laufd, laufi),
            "REGUP": self.tables.regup(laufd, laufi),
            "REGUH": self.tables.reguh(laufd, laufi),
        }

    def resolve_status_bar(self) -> dict[str, Any]:
        if self.driver is None:
            return {}
        raw = self.driver.status_bar()
        if self.messages:
            msg = self.messages.resolve_status_bar(raw)
        else:
            from sapilot.observe.messages import parse_status_bar

            msg = parse_status_bar(raw)
        return msg.model_dump()

    def screen_summary(self) -> dict[str, Any]:
        if self.driver is None:
            return {}
        snap = self.driver.snapshot()
        return {
            "tcode": snap.tcode,
            "title": snap.title,
            "status_bar": snap.status_bar or self.driver.status_bar(),
            "element_count": len(snap.element_ids()),
            "elements": self.driver.flat_elements()[:100],
        }

    def extract_visible_grid(self, table_id: str | None = None) -> dict[str, Any]:
        if self.driver is None:
            return {"rows": [], "channel": "none"}
        rows = self.driver.extract_table_control(table_id)
        return {"channel": "gui", "rows": rows, "count": len(rows), "degraded": True}

    def _se16n_read(self, table: str, rowcount: int = 50) -> dict[str, Any]:
        assert self.driver is not None
        d = self.driver
        d.start_transaction("SE16N")
        # Common field ids (release-dependent — resolve by name)
        for name in ("GD-TAB", "I_TAB", "TABNAME"):
            try:
                d.set_text(name, table.upper())
                break
            except KeyError:
                continue
        try:
            d.send_f8()
        except Exception:
            d.send_enter()
        rows = d.extract_table_control(max_rows=rowcount)
        return {
            "channel": "gui_se16n",
            "table": table,
            "rows": rows,
            "count": len(rows),
            "degraded": True,
        }
