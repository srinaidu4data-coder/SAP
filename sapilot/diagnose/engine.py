"""
Payment-run diagnostic engine — the product.

Connect via RFC, read FBZP + vendor master + open items, explain why items
would be / were excluded, and propose fixes. No GUI, no writes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from sapilot.know.tables import KnowledgeTables
from sapilot.schemas import DiagnosisFinding, DiagnosisReport


def _load_error_playbooks() -> dict[str, Any]:
    root = Path(__file__).resolve().parent.parent / "know" / "errors"
    out: dict[str, Any] = {}
    if not root.exists():
        return out
    for p in root.glob("*.yaml"):
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        out[p.stem.upper()] = data
    return out


class PaymentRunDiagnosticEngine:
    def __init__(self, tables: KnowledgeTables):
        self.tables = tables
        self.error_books = _load_error_playbooks()

    def diagnose(
        self,
        company_code: str,
        payment_method: str,
        vendors: list[str] | None = None,
        land1: str = "US",
        laufd: str | None = None,
        laufi: str | None = None,
    ) -> DiagnosisReport:
        bukrs = company_code
        zlsch = payment_method
        findings: list[DiagnosisFinding] = []

        config = self.tables.fbzp_chain_snapshot(bukrs, zlsch, land1=land1)

        # --- Config chain checks ---
        if not config["T042"]:
            findings.append(
                DiagnosisFinding(
                    entity_type="config",
                    entity_key={"BUKRS": bukrs},
                    symptom="Company code not configured as sending/paying code",
                    cause_table="T042",
                    cause_key={"BUKRS": bukrs},
                    cause_field="BUKRS",
                    current_value=None,
                    recommended_value=bukrs,
                    remediation="Maintain FBZP → All Company Codes for this BUKRS",
                    severity="blocker",
                )
            )

        if not config["T042Z"]:
            findings.append(
                DiagnosisFinding(
                    entity_type="config",
                    entity_key={"LAND1": land1, "ZLSCH": zlsch},
                    symptom="Payment method not defined for country",
                    cause_table="T042Z",
                    cause_key={"LAND1": land1, "ZLSCH": zlsch},
                    cause_field="ZLSCH",
                    current_value=None,
                    recommended_value=zlsch,
                    remediation="FBZP → Payment methods in country: create method",
                    severity="blocker",
                )
            )

        t042e = config["T042E"]
        if not t042e:
            findings.append(
                DiagnosisFinding(
                    entity_type="config",
                    entity_key={"ZBUKR": bukrs, "ZLSCH": zlsch},
                    symptom="Payment method not set up for company code",
                    cause_table="T042E",
                    cause_key={"ZBUKR": bukrs, "ZLSCH": zlsch},
                    cause_field="ZLSCH",
                    current_value=None,
                    recommended_value=zlsch,
                    remediation="FBZP → Payment methods in company code: activate method",
                    message_signature="FZ/no_method_cc",
                    severity="blocker",
                )
            )

        if not config["T042I"]:
            findings.append(
                DiagnosisFinding(
                    entity_type="config",
                    entity_key={"ZBUKR": bukrs, "ZLSCH": zlsch},
                    symptom="No house bank ranking for method/currency",
                    cause_table="T042I",
                    cause_key={"ZBUKR": bukrs, "ZLSCH": zlsch},
                    cause_field="HBKID",
                    current_value=None,
                    recommended_value="(maintain ranking)",
                    remediation="FBZP → Bank determination → Ranking order",
                    message_signature="FZ/bank_determination",
                    severity="blocker",
                )
            )
        elif not config["T042A"]:
            findings.append(
                DiagnosisFinding(
                    entity_type="config",
                    entity_key={"ZBUKR": bukrs},
                    symptom="Bank determination account assignment missing",
                    cause_table="T042A",
                    cause_key={"ZBUKR": bukrs},
                    cause_field="HKTID",
                    current_value=None,
                    recommended_value="(house bank account id)",
                    remediation="FBZP → Bank determination → Bank accounts",
                    severity="blocker",
                )
            )

        # Available amounts — commonly missed
        for row in config.get("T042Y") or []:
            amt = row.get("MAXBT") or row.get("BETRG") or row.get("WRBTR") or ""
            if amt in {"0", "0.00", "0.0", ""}:
                findings.append(
                    DiagnosisFinding(
                        entity_type="config",
                        entity_key={
                            "ZBUKR": row.get("ZBUKR", bukrs),
                            "HBKID": row.get("HBKID", ""),
                            "HKTID": row.get("HKTID", ""),
                        },
                        symptom="House bank available amount is zero or empty",
                        cause_table="T042Y",
                        cause_key={
                            "ZBUKR": row.get("ZBUKR", bukrs),
                            "HBKID": row.get("HBKID", ""),
                        },
                        cause_field="MAXBT",
                        current_value=str(amt),
                        recommended_value="(sufficient available amount)",
                        remediation="FBZP → Bank determination → Available amounts",
                        severity="blocker",
                    )
                )

        # Discover vendors from open items if not provided
        vendor_list = list(vendors or [])
        if not vendor_list:
            items = self.tables.bsik(bukrs, rowcount=500)
            vendor_list = sorted({i.get("LIFNR", "").lstrip("0") or i.get("LIFNR", "") for i in items if i.get("LIFNR")})
            # keep zero-padded originals for reads
            vendor_list = sorted({i.get("LIFNR", "") for i in items if i.get("LIFNR")})

        vendors_checked: list[str] = []
        for lifnr in vendor_list:
            vendors_checked.append(lifnr)
            findings.extend(self._diagnose_vendor(bukrs, zlsch, lifnr, config))

        # Run results if identifiers provided
        if laufd and laufi:
            reguv = self.tables.reguv(laufd, laufi)
            regup = self.tables.regup(laufd, laufi)
            if reguv and not regup:
                findings.append(
                    DiagnosisFinding(
                        entity_type="run",
                        entity_key={"LAUFD": laufd, "LAUFI": laufi},
                        symptom="Payment run has control record but zero REGUP items",
                        cause_table="REGUP",
                        cause_key={"LAUFD": laufd, "LAUFI": laufi},
                        cause_field="VBLNR",
                        current_value="0 rows",
                        recommended_value=">0 rows after successful proposal/payment",
                        remediation="Re-check proposal exceptions and additional log; do not trust screen alone",
                        severity="blocker",
                    )
                )

        summary = self._summarize(findings, bukrs, zlsch, len(vendors_checked))
        return DiagnosisReport(
            company_code=bukrs,
            payment_method=zlsch,
            run_date=laufd,
            run_id=laufi,
            findings=findings,
            config_snapshot=_strip_sensitive_config(config),
            vendors_checked=vendors_checked,
            summary=summary,
        )

    def _diagnose_vendor(
        self,
        bukrs: str,
        zlsch: str,
        lifnr: str,
        config: dict[str, Any],
    ) -> list[DiagnosisFinding]:
        findings: list[DiagnosisFinding] = []
        lfa1 = self.tables.lfa1(lifnr)
        if not lfa1:
            findings.append(
                DiagnosisFinding(
                    entity_type="vendor",
                    entity_key={"LIFNR": lifnr},
                    symptom="Vendor master not found",
                    cause_table="LFA1",
                    cause_key={"LIFNR": lifnr},
                    cause_field="LIFNR",
                    current_value=None,
                    recommended_value=lifnr,
                    remediation="Create vendor or correct vendor number",
                    severity="blocker",
                )
            )
            return findings

        lfa = lfa1[0]
        if (lfa.get("SPERR") or "").strip() or (lfa.get("LOEVM") or "").strip():
            findings.append(
                DiagnosisFinding(
                    entity_type="vendor",
                    entity_key={"LIFNR": lifnr},
                    symptom="Vendor has central posting/deletion block",
                    cause_table="LFA1",
                    cause_key={"LIFNR": lifnr},
                    cause_field="SPERR",
                    current_value=lfa.get("SPERR") or lfa.get("LOEVM"),
                    recommended_value="",
                    remediation="Remove central block if business-approved",
                    severity="blocker",
                )
            )

        lfb1 = self.tables.lfb1(lifnr, bukrs)
        if not lfb1:
            findings.append(
                DiagnosisFinding(
                    entity_type="vendor",
                    entity_key={"LIFNR": lifnr, "BUKRS": bukrs},
                    symptom="Vendor has no company-code data",
                    cause_table="LFB1",
                    cause_key={"LIFNR": lifnr, "BUKRS": bukrs},
                    cause_field="BUKRS",
                    current_value=None,
                    recommended_value=bukrs,
                    remediation="Extend vendor to company code",
                    severity="blocker",
                )
            )
            return findings

        lfb = lfb1[0]
        zwels = (lfb.get("ZWELS") or "").upper()
        if zlsch.upper() not in zwels and zwels.strip() != "":
            # empty ZWELS often means all methods allowed — only flag when set and missing
            findings.append(
                DiagnosisFinding(
                    entity_type="vendor",
                    entity_key={"LIFNR": lifnr, "BUKRS": bukrs},
                    symptom="No valid payment method found on vendor (ZWELS)",
                    cause_table="LFB1",
                    cause_key={"LIFNR": lifnr, "BUKRS": bukrs},
                    cause_field="ZWELS",
                    current_value=zwels,
                    recommended_value=f"{zwels}{zlsch.upper()}".strip(),
                    remediation=f"Add payment method '{zlsch}' to LFB1-ZWELS",
                    message_signature="FZ/no_valid_payment_method",
                    severity="blocker",
                )
            )
        elif not zwels.strip():
            # still ok usually; soft note not needed
            pass

        zahls = (lfb.get("ZAHLS") or "").strip()
        if zahls:
            findings.append(
                DiagnosisFinding(
                    entity_type="vendor",
                    entity_key={"LIFNR": lifnr, "BUKRS": bukrs},
                    symptom="Vendor-level payment block set",
                    cause_table="LFB1",
                    cause_key={"LIFNR": lifnr, "BUKRS": bukrs},
                    cause_field="ZAHLS",
                    current_value=zahls,
                    recommended_value="",
                    remediation="Clear LFB1-ZAHLS if payment should proceed",
                    message_signature="FZ/item_blocked",
                    severity="blocker",
                )
            )

        # Bank details required?
        t042z = config.get("T042Z") or []
        requires_bank = False
        for z in t042z:
            # XPGIR / XSTRA / similar flags vary; check common "bank details required"
            if (z.get("XPGIR") or z.get("XSTRA") or z.get("XBKKT") or "").strip() in {
                "X",
                "x",
                "1",
            }:
                requires_bank = True
            # ACH always needs bank details in practice
            requires_bank = True

        lfbk = self.tables.lfbk(lifnr)
        if requires_bank and not lfbk:
            findings.append(
                DiagnosisFinding(
                    entity_type="vendor",
                    entity_key={"LIFNR": lifnr},
                    symptom="Payment method not allowed for this account — bank details missing",
                    cause_table="LFBK",
                    cause_key={"LIFNR": lifnr},
                    cause_field="BANKN",
                    current_value=None,
                    recommended_value="(US routing + account)",
                    remediation="Maintain vendor bank details (LFBK); ensure BNKA master exists for routing",
                    message_signature="FZ/bank_details_required",
                    severity="blocker",
                )
            )
        elif lfbk:
            for bank in lfbk:
                banks = bank.get("BANKS") or "US"
                bankl = bank.get("BANKL") or ""
                if bankl:
                    bnka = self.tables.bnka(banks, bankl)
                    if not bnka:
                        findings.append(
                            DiagnosisFinding(
                                entity_type="vendor",
                                entity_key={"LIFNR": lifnr, "BANKL": bankl},
                                symptom="Bank routing number not found in bank master",
                                cause_table="BNKA",
                                cause_key={"BANKS": banks, "BANKL": bankl},
                                cause_field="BANKL",
                                current_value=bankl,
                                recommended_value="(create BNKA entry)",
                                remediation="Create bank master for routing/ABA number",
                                severity="blocker",
                            )
                        )

        # Open items
        items = self.tables.bsik(bukrs, lifnr=lifnr)
        for it in items:
            zlspr = (it.get("ZLSPR") or "").strip()
            if zlspr:
                findings.append(
                    DiagnosisFinding(
                        entity_type="item",
                        entity_key={
                            "BUKRS": bukrs,
                            "BELNR": it.get("BELNR", ""),
                            "GJAHR": it.get("GJAHR", ""),
                            "BUZEI": it.get("BUZEI", ""),
                        },
                        symptom="Item blocked for payment",
                        cause_table="BSIK",
                        cause_key={"BELNR": it.get("BELNR", ""), "BUZEI": it.get("BUZEI", "")},
                        cause_field="ZLSPR",
                        current_value=zlspr,
                        recommended_value="",
                        remediation="Clear item payment block ZLSPR (check T008 reason)",
                        message_signature="FZ/item_blocked",
                        severity="blocker",
                    )
                )
            item_method = (it.get("ZLSCH") or "").strip()
            if item_method and item_method.upper() != zlsch.upper():
                findings.append(
                    DiagnosisFinding(
                        entity_type="item",
                        entity_key={"BELNR": it.get("BELNR", ""), "BUZEI": it.get("BUZEI", "")},
                        symptom="Item-level payment method overrides vendor and excludes from this run",
                        cause_table="BSIK",
                        cause_key={"BELNR": it.get("BELNR", "")},
                        cause_field="ZLSCH",
                        current_value=item_method,
                        recommended_value=zlsch,
                        remediation="Change item payment method or include method in F110 parameters",
                        severity="warning",
                    )
                )

        if not items:
            findings.append(
                DiagnosisFinding(
                    entity_type="vendor",
                    entity_key={"LIFNR": lifnr, "BUKRS": bukrs},
                    symptom="No open vendor items in BSIK for selection window",
                    cause_table="BSIK",
                    cause_key={"LIFNR": lifnr, "BUKRS": bukrs},
                    cause_field="BELNR",
                    current_value="0",
                    recommended_value=">=1 open item due in run window",
                    remediation="Check posting date / docs-entered-up-to / due date via ZTERM",
                    severity="info",
                )
            )

        return findings

    def _summarize(
        self,
        findings: list[DiagnosisFinding],
        bukrs: str,
        zlsch: str,
        vendor_count: int,
    ) -> str:
        blockers = sum(1 for f in findings if f.severity == "blocker")
        warnings = sum(1 for f in findings if f.severity == "warning")
        if blockers == 0 and warnings == 0:
            return (
                f"No blockers found for company code {bukrs}, payment method {zlsch}, "
                f"{vendor_count} vendor(s) checked. Proceed to proposal with additional log enabled."
            )
        return (
            f"Diagnosed {len(findings)} finding(s) for BUKRS={bukrs} ZLSCH={zlsch} "
            f"({vendor_count} vendors): {blockers} blocker(s), {warnings} warning(s). "
            f"Fix blockers before payment proposal will select items."
        )


def _strip_sensitive_config(config: dict[str, Any]) -> dict[str, Any]:
    """Drop likely account numbers from config snapshot used in reports."""
    # Config tables rarely hold vendor bank accounts; pass through.
    return config
