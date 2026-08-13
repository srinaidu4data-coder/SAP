"""
Optional example scripts on top of HumanEyesHands.

The operator itself is process-agnostic. This file may hold sample
sequences (a PO, a journal entry, a sales order) for demos. Adding a
sample here does not make that process the product.
"""

from __future__ import annotations

from dataclasses import dataclass

from sapilot.autobot.operator import ActResult, HumanEyesHands

# Keys that exist on APEX-2023 / client 100. Change only after SE16N.
DEFAULT_PO = {
    "vendor": "USSU-VSF01",
    "ekorg": "1710",
    "ekgrp": "002",
    "bukrs": "1710",
    "material": "TG10",
    "qty": "10",
    "uom": "PC",
    "deliv": "08/31/2026",
    "price": "10",
    "curr": "USD",
    "plant": "1710",
    "knttp": "K",
    "kostl": "1710-10",
}


@dataclass
class PlaybookOutcome:
    ok: bool
    steps: list[ActResult]
    claimed_doc: str | None = None
    proof: str = ""


def run_me21n(op: HumanEyesHands, keys: dict[str, str] | None = None) -> PlaybookOutcome:
    """
    Create a Standard PO like a buyer: command box → vendor → org → item → save
    → prove in EKKO. If EKKO has no row, we did not create a PO.
    """
    k = {**DEFAULT_PO, **(keys or {})}
    steps: list[ActResult] = []

    steps.append(op.goto("ME21N"))
    steps.append(op.fill_label(["Supplier"], k["vendor"], enter=True))
    steps.append(op.click_label(["Header"], side="below"))
    steps.append(op.click_label(["Org. Data", "Org Data", "Purch. Org"]))
    steps.append(op.fill_label(["Purch. Org", "Purchasing Organization"], k["ekorg"]))
    steps.append(op.fill_label(["Purch. Group", "Purchasing Group"], k["ekgrp"]))
    steps.append(op.fill_label(["Company Code", "Company"], k["bukrs"], enter=True))
    steps.append(op.click_label(["Item Overview"], side="below"))
    steps.append(op.fill_label(["Material"], k["material"]))
    steps.append(op.fill_label(["Quantity", "PO Quantity"], k["qty"]))
    steps.append(op.fill_label(["Deliv", "Delivery"], k["deliv"]))
    steps.append(op.fill_label(["Net Price", "Price"], k["price"]))
    steps.append(op.fill_label(["Plant"], k["plant"]))
    steps.append(op.fill_label(["A", "Acct", "Account Assignment"], k["knttp"]))
    steps.append(op.fill_label(["Cost Center", "Cost Ctr"], k["kostl"]))
    saved = op.save_doc()
    steps.append(saved)

    hint = saved.view.status.docno if saved.view and saved.view.status else None
    if not hint:
        return PlaybookOutcome(False, steps, None, "No document number on the status bar. Not proven.")

    proof = op.prove_in_table("EKKO", "Purchasing Doc", hint)
    steps.append(proof)
    if not proof.claimed:
        return PlaybookOutcome(False, steps, None, proof.detail)
    return PlaybookOutcome(True, steps, hint, proof.detail)


def run_see(op: HumanEyesHands) -> PlaybookOutcome:
    view = op.see("manual")
    detail = f"{len(view.words)} words"
    if view.status and view.status.text:
        detail += f" | status: {view.status.kind} {view.status.text}"
    return PlaybookOutcome(True, [ActResult(True, "see", detail, view)], None, detail)
