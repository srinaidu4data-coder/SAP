"""Display-wing cycles. PTP / OTC / CO-PC are examples. The product is the spine.

Each cycle is org → master → transactional display → financial display.
Keys are placeholders filled at walk time. Missing keys: still open the
display t-code and photograph the initial Display screen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DisplayStep:
    id: str
    phase: str  # org | master | transaction | flow | financial
    tcode: str
    purpose: str
    # (label aliases, key name). key name looked up in walk keys.
    fields: tuple[tuple[tuple[str, ...], str], ...] = ()
    enter_after: bool = True
    execute: bool = False  # F8 for list/report (still display)
    expect_in_title: tuple[str, ...] = ("Display",)
    drill_label: str | None = None  # optional on-screen hop, e.g. Document flow
    notes: str = ""


@dataclass(frozen=True)
class DisplayCycle:
    name: str
    title: str
    spine: str
    default_keys: dict[str, str] = field(default_factory=dict)
    steps: tuple[DisplayStep, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "spine": self.spine,
            "steps": [
                {
                    "id": s.id,
                    "phase": s.phase,
                    "tcode": s.tcode,
                    "purpose": s.purpose,
                    "keys": [k for _labels, k in s.fields],
                    "notes": s.notes,
                }
                for s in self.steps
            ],
        }


# Existing documents on APEX-2023 / client 100. Looked at, not created here.
_APEX = {
    "bukrs": "1710",
    "werks": "1710",
    "ekorg": "1710",
    "ekgrp": "002",
    "vkorg": "1710",
    "vendor": "USSU-VSF01",
    "material": "TG10",
    "pr": "10014061",
    "po": "4500000002",
    "kostl": "1710-10",
}


PTP = DisplayCycle(
    name="ptp",
    title="Procure-to-Pay (example cycle)",
    spine="org → vendor → material → PR → PO → GR doc → IR doc → vendor line",
    default_keys={**_APEX, "table_t001": "T001", "mblnr": "", "rebzp": ""},
    steps=(
        DisplayStep(
            "org_company",
            "org",
            "SE16N",
            "Enterprise: company code row (table display, not OX02 customizing)",
            fields=((("Data base", "base:"), "table_t001"),),
            notes="table_t001 defaults to T001. Filter 1710 on glass if the field is there.",
        ),
        DisplayStep(
            "master_vendor",
            "master",
            "XK03",
            "Display supplier / vendor (S/4 may land on Display Business Partner)",
            fields=((("Vendor", "Supplier", "Business Partner"), "vendor"),),
            expect_in_title=("Display", "Supplier", "Vendor", "Business Partner"),
        ),
        DisplayStep(
            "master_material",
            "master",
            "MM03",
            "Display material master",
            fields=((("Material",), "material"),),
            expect_in_title=("Display Material", "Material"),
        ),
        DisplayStep(
            "tx_pr",
            "transaction",
            "ME53N",
            "Display purchase requisition (existing number)",
            fields=((("Purchase Requisition", "Requisition", "Number"), "pr"),),
            expect_in_title=("Purchase Req", "Requisition", "Display Purchase"),
        ),
        DisplayStep(
            "tx_po",
            "transaction",
            "ME23N",
            "Display purchase order (existing number)",
            fields=((("Purchase Order", "Purchasing Document", "PO"), "po"),),
            expect_in_title=("Purchase Order", "Stock Transp. Order", "Stock Transp"),
            drill_label="Document Overview",
        ),
        DisplayStep(
            "tx_gr",
            "transaction",
            "MB03",
            "Display material document (GR). Never MIGO.",
            fields=((("Material Document", "Document"), "mblnr"),),
            expect_in_title=("Material Document", "Display Material"),
            notes="Skip fill if mblnr unknown — still prove MB03 is Display.",
        ),
        DisplayStep(
            "tx_ir",
            "transaction",
            "MIR4",
            "Display incoming invoice. Never MIRO.",
            fields=((("Invoice Document", "Invoice", "Document Number"), "rebzp"),),
            expect_in_title=("Invoice", "Display Invoice"),
        ),
        DisplayStep(
            "fi_vendor",
            "financial",
            "FBL1N",
            "Vendor line item display (report, not a post)",
            fields=(
                (("Vendor", "Supplier"), "vendor"),
                (("Company Code", "Company"), "bukrs"),
            ),
            execute=True,
            expect_in_title=("Line Item", "Vendor Line"),
        ),
    ),
)


OTC = DisplayCycle(
    name="otc",
    title="Order-to-Cash (example cycle)",
    spine="org → customer → material → sales order → delivery → billing → AR line",
    default_keys={
        **_APEX,
        "table_tvko": "TVKO",
        "customer": "",
        "vbeln": "",
        "delivery": "",
        "billing": "",
    },
    steps=(
        DisplayStep(
            "org_sales",
            "org",
            "SE16N",
            "Enterprise: sales organizations (table display)",
            fields=((("Data base", "base:"), "table_tvko"),),
        ),
        DisplayStep(
            "master_customer",
            "master",
            "XD03",
            "Display customer. Empty key → photograph Display initial screen.",
            fields=((("Customer", "Account"), "customer"),),
        ),
        DisplayStep(
            "master_material",
            "master",
            "MM03",
            "Display material (sales views live on MVKE)",
            fields=((("Material",), "material"),),
        ),
        DisplayStep(
            "tx_so",
            "transaction",
            "VA03",
            "Display sales order. Empty vbeln → Display Sales Documents initial.",
            fields=((("Order", "Sales Document", "Document"), "vbeln"),),
            drill_label="Document flow",
        ),
        DisplayStep(
            "tx_so_list",
            "transaction",
            "VA05",
            "Sales order list (display). Execute if org is filled.",
            fields=((("Sold-to party", "Customer"), "customer"),),
            execute=True,
        ),
        DisplayStep(
            "tx_dn",
            "transaction",
            "VL03N",
            "Display outbound delivery. Never VL01N/VL02N.",
            fields=((("Delivery", "Outbound Delivery"), "delivery"),),
        ),
        DisplayStep(
            "tx_bill",
            "transaction",
            "VF03",
            "Display billing document. Never VF01.",
            fields=((("Billing Document", "Billing"), "billing"),),
        ),
        DisplayStep(
            "fi_ar",
            "financial",
            "FBL5N",
            "Customer line item display",
            fields=(
                (("Customer",), "customer"),
                (("Company Code", "Company"), "bukrs"),
            ),
            execute=True,
        ),
    ),
)


COPC = DisplayCycle(
    name="copc",
    title="Product Costing (example cycle)",
    spine="CO area → cost center → material price → estimate → prod order → ML",
    default_keys={
        **_APEX,
        "table_tka02": "TKA02",
        "kokrs": "",
        "aufnr": "",
    },
    steps=(
        DisplayStep(
            "org_co",
            "org",
            "SE16N",
            "Enterprise: company ↔ controlling area (TKA02)",
            fields=((("Data base", "base:"), "table_tka02"),),
        ),
        DisplayStep(
            "master_cc",
            "master",
            "KS03",
            "Display cost center 1710-10 (used on PTP account assignment)",
            fields=((("Cost Center",), "kostl"),),
            expect_in_title=("Cost Center", "Display Cost"),
        ),
        DisplayStep(
            "master_material",
            "master",
            "MM03",
            "Display material — Accounting / Costing views",
            fields=((("Material",), "material"),),
            expect_in_title=("Display Material", "Material"),
        ),
        DisplayStep(
            "tx_estimate",
            "transaction",
            "CK13N",
            "Display cost estimate. Never CK11N / CK24.",
            fields=(
                (("Material",), "material"),
                (("Plant",), "werks"),
            ),
            expect_in_title=("Cost Estimate", "Display Material Cost"),
        ),
        DisplayStep(
            "tx_order",
            "transaction",
            "CO03",
            "Display production order. Empty aufnr → Display initial screen.",
            fields=((("Order",), "aufnr"),),
            expect_in_title=("Production Order", "Display Order", "Process Order"),
        ),
        DisplayStep(
            "tx_ml",
            "transaction",
            "CKM3N",
            "Material price analysis (display). Never CKMLCP.",
            fields=(
                (("Material",), "material"),
                (("Plant",), "werks"),
            ),
            expect_in_title=("Price Analysis", "Material Price", "CKM3"),
        ),
    ),
)


R2R = DisplayCycle(
    name="r2r",
    title="Record-to-Report (example cycle)",
    spine="company → G/L account → FI document → G/L line",
    default_keys={**_APEX, "table_t001": "T001", "hkont": "610000", "belnr": "", "gjahr": "2018"},
    steps=(
        DisplayStep(
            "org_company",
            "org",
            "SE16N",
            "Enterprise: company code T001",
            fields=((("Data base", "base:"), "table_t001"),),
        ),
        DisplayStep(
            "master_gl",
            "master",
            "FS03",
            "Display G/L account. Never FS00.",
            fields=(
                (("G/L Account", "Account"), "hkont"),
                (("Company Code",), "bukrs"),
            ),
        ),
        DisplayStep(
            "tx_fi",
            "transaction",
            "FB03",
            "Display FI document. Never FB50/FB01.",
            fields=(
                (("Document Number", "Document"), "belnr"),
                (("Company Code",), "bukrs"),
                (("Fiscal Year", "Year"), "gjahr"),
            ),
        ),
        DisplayStep(
            "fi_gl",
            "financial",
            "FBL3N",
            "G/L line item display",
            fields=(
                (("G/L Account", "Account"), "hkont"),
                (("Company Code",), "bukrs"),
            ),
            execute=True,
        ),
    ),
)


COLLECTIONS = DisplayCycle(
    name="collections",
    title="Collections / AR (example cycle)",
    spine="customer → AR line → credit display → billing display",
    default_keys={**_APEX, "customer": "", "billing": ""},
    steps=(
        DisplayStep(
            "master_customer",
            "master",
            "XD03",
            "Display customer",
            fields=((("Customer",), "customer"),),
        ),
        DisplayStep(
            "fi_ar",
            "financial",
            "FBL5N",
            "Open / all customer items (display report)",
            fields=(
                (("Customer",), "customer"),
                (("Company Code",), "bukrs"),
            ),
            execute=True,
        ),
        DisplayStep(
            "master_credit",
            "master",
            "FD33",
            "Display credit master. Never FD32. KNKK was 0 on this system.",
            fields=((("Customer",), "customer"),),
        ),
        DisplayStep(
            "tx_bill",
            "transaction",
            "VF03",
            "Display billing document",
            fields=((("Billing Document",), "billing"),),
        ),
    ),
)


CYCLES: dict[str, DisplayCycle] = {
    c.name: c for c in (PTP, OTC, COPC, R2R, COLLECTIONS)
}


def cycle_names() -> list[str]:
    return list(CYCLES)


def get_cycle(name: str) -> DisplayCycle:
    key = (name or "").strip().lower()
    if key not in CYCLES:
        raise KeyError(f"unknown cycle {name!r}; have {cycle_names()}")
    return CYCLES[key]
