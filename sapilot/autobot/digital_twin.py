"""
Digital twin of SAP PTP landscape — invents missing master/transactional data
when live writes are blocked, so the bot can still complete consultant workflows.

When live RFC/BAPI becomes available, the same create_* methods map to BAPIs
(e.g. BAPI_PO_CREATE1) — research-standard path for PO automation.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from sapilot.connect.rfc import MockRfcClient
from sapilot.demo_data_abap import seed_abap_tables
from sapilot.demo_data_otc import seed_otc_tables
from sapilot.demo_data_ptp import seed_ptp_tables

log = logging.getLogger(__name__)


class DigitalTwin:
    """In-memory S/4-like store the bot can read/write like a sandbox client."""

    def __init__(self) -> None:
        self.rfc = MockRfcClient()
        seed_ptp_tables(self.rfc)
        seed_otc_tables(self.rfc)
        seed_abap_tables(self.rfc)
        self.created: list[dict[str, Any]] = []
        self.audit: list[str] = []

    def note(self, msg: str) -> None:
        self.audit.append(msg)
        log.info("TWIN: %s", msg)

    def read(self, table: str, options: list[str] | None = None) -> list[dict[str, str]]:
        return self.rfc.read_table(table, options=options, rowcount=500)

    def ensure_vendor_payment_ready(self, lifnr: str = "0000100001", bukrs: str = "1000", method: str = "A") -> list[str]:
        """Consultant fix: ZWELS, clear ZAHLS, add LFBK, fix FBZP gaps."""
        fixes: list[str] = []
        # LFB1
        rows = self.read("LFB1", [f"LIFNR = '{lifnr}'", f"AND BUKRS = '{bukrs}'"])
        if rows:
            r = dict(rows[0])
            if method.upper() not in (r.get("ZWELS") or "").upper():
                r["ZWELS"] = (r.get("ZWELS") or "") + method.upper()
                fixes.append(f"LFB1-ZWELS += {method}")
            if (r.get("ZAHLS") or "").strip():
                r["ZAHLS"] = ""
                fixes.append("LFB1-ZAHLS cleared")
            self.rfc.seed("LFB1", [r])
        # LFBK
        banks = self.read("LFBK", [f"LIFNR = '{lifnr}'"])
        if not banks:
            self.rfc.seed(
                "LFBK",
                [
                    {
                        "LIFNR": lifnr,
                        "BANKS": "US",
                        "BANKL": "021000021",
                        "BANKN": "9876543210",
                        "BVTYP": "0001",
                        "KOINH": "DEMO VENDOR",
                    }
                ],
            )
            fixes.append("LFBK bank details created")
        # BSIK clear item block on non-demo or all
        bsik = self.read("BSIK", [f"BUKRS = '{bukrs}'", f"AND LIFNR = '{lifnr}'"])
        cleaned = []
        for r in bsik:
            rr = dict(r)
            if (rr.get("ZLSPR") or "").strip():
                rr["ZLSPR"] = ""
                fixes.append(f"BSIK {rr.get('BELNR')} ZLSPR cleared")
            if method.upper() not in (rr.get("ZLSCH") or method).upper():
                rr["ZLSCH"] = method
            cleaned.append(rr)
        if cleaned:
            self.rfc.seed("BSIK", cleaned)
        # FBZP
        self.rfc.seed(
            "T042E",
            [
                {
                    "ZBUKR": bukrs,
                    "ZLSCH": method,
                    "XBKKT": "",
                    "XEOSC": "",
                    "XELGB": "",
                    "VONBT": "0",
                    "BISBT": "999999999",
                    "WAERS": "USD",
                }
            ],
        )
        fixes.append("T042E payment method activated")
        self.rfc.seed(
            "T042I",
            [{"ZBUKR": bukrs, "ZLSCH": method, "WAERS": "USD", "HBKID": "HOME", "HKTID": "OPER", "RANGF": "1"}],
        )
        fixes.append("T042I ranking created")
        self.rfc.seed(
            "T042A",
            [{"ZBUKR": bukrs, "HBKID": "HOME", "HKTID": "OPER", "WAERS": "USD", "ZLSCH": method}],
        )
        self.rfc.seed(
            "T042Y",
            [{"ZBUKR": bukrs, "HBKID": "HOME", "HKTID": "OPER", "MAXBT": "9999999.00"}],
        )
        fixes.append("T042Y available amount set")
        self.created.append({"kind": "payment_ready", "fixes": fixes})
        self.note("Payment readiness fixed: " + "; ".join(fixes))
        return fixes

    def ensure_po_chain(self) -> dict[str, str]:
        """Ensure PR/PO/GR/IR exist; create missing documents."""
        ids = {
            "lifnr": "0000100001",
            "bukrs": "1000",
            "matnr": "000000000000100000",
            "ebeln": "4500000001",
            "banfn": "0010000001",
            "belnr_inv": "5105600001",
        }
        if not self.read("EKKO", [f"EBELN = '{ids['ebeln']}'"]):
            # reseed full ptp
            seed_ptp_tables(self.rfc)
            self.note("Reseeded full PTP chain")
        return ids

    def ensure_otc_chain(self) -> dict[str, str]:
        """Ensure SO → DN → Billing → AR open item exist."""
        ids = {
            "kunnr": "0000001000",
            "bukrs": "1000",
            "vkorg": "1000",
            "vtweg": "10",
            "spart": "00",
            "matnr": "000000000000100000",
            "vbeln_so": "0000001001",
            "vbeln_dn": "0080001001",
            "vbeln_bill": "0090001001",
        }
        if not self.read("VBAK", [f"VBELN = '{ids['vbeln_so']}'"]):
            seed_otc_tables(self.rfc)
            self.note("Reseeded full OTC chain")
        return ids

    def ensure_abap_debug_ready(self) -> list[str]:
        """Ensure ST22/SE38 twin data exists for ABAP debug missions."""
        fixes: list[str] = []
        if not self.read("SNAP_BEG"):
            seed_abap_tables(self.rfc)
            fixes.append("Reseeded ABAP dump + program catalog")
        if not self.read("TRDIR", ["NAME = 'ZSAP_DEMO_INVOICE'"]):
            seed_abap_tables(self.rfc)
            fixes.append("Reseeded TRDIR programs")
        if not fixes:
            fixes.append("ABAP debug landscape already ready")
        self.note("ABAP debug ready: " + "; ".join(fixes))
        return fixes

    def ensure_customer_payment_ready(self, kunnr: str = "0000001000", bukrs: str = "1000") -> list[str]:
        fixes: list[str] = []
        knb1 = self.read("KNB1", [f"KUNNR = '{kunnr}'", f"AND BUKRS = '{bukrs}'"])
        if knb1:
            r = dict(knb1[0])
            if (r.get("SPERR") or "").strip():
                r["SPERR"] = ""
                fixes.append("KNB1 posting block cleared")
            self.rfc.seed("KNB1", [r])
        bsid = self.read("BSID", [f"BUKRS = '{bukrs}'", f"AND KUNNR = '{kunnr}'"])
        cleaned = []
        for row in bsid:
            rr = dict(row)
            if (rr.get("ZLSPR") or "").strip():
                rr["ZLSPR"] = ""
                fixes.append(f"BSID {rr.get('BELNR')} block cleared")
            cleaned.append(rr)
        if cleaned:
            self.rfc.seed("BSID", cleaned)
        if not fixes:
            fixes.append("Customer AR already payment-ready")
        self.created.append({"kind": "otc_payment_ready", "fixes": fixes})
        self.note("OTC payment ready: " + "; ".join(fixes))
        return fixes

    def create_extra_po(self, ebeln: str = "4500000099") -> str:
        """Simulate BAPI_PO_CREATE1 result in twin."""
        self.rfc.seed(
            "EKKO",
            self.read("EKKO")
            + [
                {
                    "EBELN": ebeln,
                    "BUKRS": "1000",
                    "BSTYP": "F",
                    "BSART": "NB",
                    "STATU": "9",
                    "LIFNR": "0000100001",
                    "EKORG": "1000",
                    "EKGRP": "001",
                    "WAERS": "USD",
                    "BEDAT": "20260812",
                    "FRGKE": "",
                    "FRGZU": "",
                    "LOEKZ": "",
                }
            ],
        )
        self.rfc.seed(
            "EKPO",
            self.read("EKPO")
            + [
                {
                    "EBELN": ebeln,
                    "EBELP": "00010",
                    "MATNR": "000000000000100000",
                    "WERKS": "1000",
                    "LGORT": "0001",
                    "MENGE": "10",
                    "MEINS": "EA",
                    "NETPR": "12.50",
                    "PEINH": "1",
                    "NETWR": "125.00",
                    "MWSKZ": "I0",
                    "KNTTP": "",
                    "LOEKZ": "",
                    "ELIKZ": "",
                    "EREKZ": "",
                }
            ],
        )
        self.note(f"Created PO {ebeln} (twin = BAPI_PO_CREATE1 analog)")
        self.created.append({"kind": "PO", "ebeln": ebeln})
        return ebeln
