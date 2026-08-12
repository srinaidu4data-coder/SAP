"""
Inject extracted / prepared data into live SAP GUI screens.

Maps table field values → screen fields (by technical name) and types them
with visible mouse movement when enabled.
"""

from __future__ import annotations

import logging
from typing import Any

from sapilot.connect.driver import GuiDriver

log = logging.getLogger(__name__)


# Common screen field mappings: logical key → SAP GUI name fragments to try
FIELD_ALIASES: dict[str, list[str]] = {
    "LIFNR": ["LIFNR", "RF02K-LIFNR", "KD_LIFNR-LOW", "VENDOR"],
    "BUKRS": ["BUKRS", "RF02K-BUKRS", "KD_BUKRS-LOW", "COMP_CODE"],
    "EBELN": ["EBELN", "MEPO_SELECT-EBELN", "PO_NUMBER"],
    "BANFN": ["BANFN", "BANFN_LOW", "NUMBER"],
    "MATNR": ["MATNR", "MATERIAL", "MATNR_LOW"],
    "WERKS": ["WERKS", "PLANT", "WERKS_LOW"],
    "EKORG": ["EKORG", "PURCH_ORG"],
    "LAUFD": ["LAUFD", "F110V-LAUFD", "RUN_DATE"],
    "LAUFI": ["LAUFI", "F110V-LAUFI", "IDENTIFICATION"],
    "BELNR": ["BELNR", "BELNR_LOW", "DOC_NUMBER"],
    "GJAHR": ["GJAHR", "GJAHR_LOW", "FISC_YEAR"],
}


class DataInjector:
    def __init__(self, driver: GuiDriver):
        self.driver = driver
        self.log: list[dict[str, Any]] = []

    def inject_map(self, values: dict[str, str]) -> dict[str, Any]:
        """
        Put real values into the current SAP screen.
        values keys are SAP technical names (LIFNR, BUKRS, …).
        Goes through WriteGuard (policy + tcode pollution block).
        """
        from sapilot.policy.guard import authorize_write

        results = []
        for key, value in values.items():
            if value is None or str(value).strip() == "":
                continue
            val = str(value).strip()
            # Pre-authorize inject (also blocks /nF110 into LIFNR)
            authorize_write("inject", target=key, value=val, logical=f"inject:{key}")
            placed = self._set_field(key, val)
            results.append({"field": key, "value": value, "ok": placed is not None, "target": placed})
            self.log.append(results[-1])
        return {"injected": results, "ok": any(r["ok"] for r in results)}

    def inject_from_table_row(
        self, row: dict[str, str], fields: list[str] | None = None
    ) -> dict[str, Any]:
        keys = fields or list(row.keys())
        values = {k: row.get(k, "") for k in keys if k in row}
        return self.inject_map(values)

    def inject_from_pack(
        self,
        pack_tables: dict[str, Any],
        preferred_table: str,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Take first row of a gathered table and type into GUI."""
        slice_ = pack_tables.get(preferred_table) or {}
        rows = slice_.get("rows") if isinstance(slice_, dict) else None
        if not rows:
            return {"ok": False, "error": f"No rows in {preferred_table} to inject"}
        return self.inject_from_table_row(rows[0], fields)

    def _set_field(self, technical: str, value: str) -> str | None:
        aliases = FIELD_ALIASES.get(technical.upper(), [technical])
        for name in aliases:
            try:
                self.driver.set_text(name, value)
                log.info("Injected %s → %s (%s)", technical, name, value[:40])
                return name
            except KeyError:
                continue
            except Exception as e:
                log.debug("inject %s via %s failed: %s", technical, name, e)
        # last resort: exact id if present on screen
        try:
            self.driver.set_text(technical, value)
            return technical
        except Exception:
            return None
