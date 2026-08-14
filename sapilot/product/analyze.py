"""Turn any process name into analysis + a display-only spine.

Catalog names are examples. Unknown names still get a walkable plan.
"""
from __future__ import annotations

from sapilot.display.catalog import CYCLES, get_cycle
from sapilot.display.policy import DisplayPolicyError, assert_display_tcode

# Example libraries only — used when the user's words match. Not the product.
_ALIASES = {
    "ptp": "ptp",
    "p2p": "ptp",
    "procure": "ptp",
    "purchase": "ptp",
    "buy": "ptp",
    "otc": "otc",
    "o2c": "otc",
    "order to cash": "otc",
    "sales": "otc",
    "sell": "otc",
    "copc": "copc",
    "costing": "copc",
    "product cost": "copc",
    "co-pc": "copc",
    "r2r": "r2r",
    "record to report": "r2r",
    "finance close": "r2r",
    "gl": "r2r",
    "collect": "collections",
    "collections": "collections",
    "ar": "collections",
    "dunning": "collections",
    "dispute": "collections",
    "rar": "rar",
    "revenue accounting": "rar",
    "revenue recognition": "rar",
    "ifrs 15": "rar",
    "ifrs15": "rar",
    "asc 606": "rar",
    "asc606": "rar",
    "farr": "rar",
}

# Display-only t-codes for processes not in the five examples.
_LIBRARY: dict[str, dict] = {
    "rar": {
        "title": "Revenue Accounting and Reporting (your process)",
        "spine": "sales contract / order → customer invoice → RAI → performance obligation → fulfill → recognize / defer → FI",
        "story": (
            "RAR is not “another billing t-code.” It is the IFRS 15 / ASC 606 layer "
            "between the customer invoice and the P&L. The sales invoice can post and "
            "still not be revenue. Revenue sits on performance obligations until a "
            "fulfillment event says it is earned. If RAR is on for company 1710, the "
            "5,982 customer invoices are the *input* to RAR, not the recognition event. "
            "Cash collection (unpaid invoices) and RAR (when revenue hits the P&L) are "
            "two clocks. Mixing them is how Finance and Sales argue past each other."
        ),
        "hops": [
            "Sales order / contract → billing document → Revenue Accounting Item (RAI)",
            "RAI processed → RAR contract and performance obligations (what we promised)",
            "Fulfillment event (goods issue, time, milestone) → revenue schedule",
            "Transfer to FI → recognized revenue and/or deferral on the balance sheet",
            "Association: unbilled deliveries never create RAI; unpaid invoices are cash, not RAR",
        ],
        "questions": [
            "Is RAR active for company 1710, or is billing still classic revenue?",
            "For one billed document: did a RAI appear? Was it processed or stuck?",
            "Do performance obligations match what was sold (one POB or many)?",
            "How much is deferred vs recognized this period?",
            "If RAI is missing, is the billing type excluded from RAR, or is the inbound job not run?",
            "Can you display one RAR contract and walk to its FI document without posting?",
        ],
        "scenarios": [
            "Point-in-time (goods): the customer invoice is not revenue until a fulfillment event (usually goods issue). If VF03 exists and FARR_RAI_MON has no RAI, the billing type is excluded or the inbound job is dead — not a collections problem.",
            "Over-time (service / subscription): RAR builds a schedule. Classic SD can still bill monthly while RAR defers the unearned piece. Mixing those two clocks is how Sales ‘revenue’ disagrees with Finance.",
            "Bundle: one sales order, many performance obligations, different recognition clocks. One revenue account for the whole bundle hides which promise was earned.",
            "Returns / credit memo: classic AR credit is the cash clock. RAR must reverse or reallocate the POB. A credit without a RAR reversal leaves recognized revenue too high.",
            "Unbilled vs deferred (do not mix): unbilled delivery = OTC, no invoice, no RAI yet. Deferred = RAI exists, not earned. 7,959 deliveries vs 5,982 bills is the unbilled gap. RAR only starts after the bill.",
            "Variable consideration / rebate: estimated variable amount sits in RAR, not in the SD invoice net. If you only look at VF03, you will overstate the P&L.",
        ],
        "tcodes": [
            ("VA03", "transaction", "Display the sales order — the commercial promise RAR will split into POBs"),
            ("VF03", "transaction", "Display the customer invoice — this should spawn a RAI if RAR is on"),
            ("FARR_RAI_MON", "transaction", "RAI monitor — display whether the invoice made it into RAR"),
            ("SE16N", "org", "RAR tables (contract, POB, deferral, revenue) — Number of Entries, then one key"),
            ("FB03", "financial", "FI after revenue transfer — recognized vs deferred"),
            ("FBL5N", "financial", "Customer open items — cash clock, not the RAR clock"),
        ],
    },
    "treasury": {
        "title": "Treasury / cash (your words)",
        "spine": "company → house bank → deals / positions → flows → FI",
        "story": "Treasury is cash and risk, not a purchase order. Ask: which company holds the deal, which house bank, what product type, and whether a flow already posted to FI.",
        "hops": [
            "Company → house bank → account → G/L",
            "Deal display → position flow → FI document",
            "If create-deal is denied, the book is still readable in tables and flow reports",
        ],
        "questions": [
            "Which company is the cash owner?",
            "Do house banks exist for that company?",
            "Have any deals already posted flows?",
            "Is payment a treasury product or AP (F110) — do not mix them?",
        ],
        "tcodes": [
            ("SE16N", "org", "Company / bank / deal tables — look, do not list 500 as a count"),
            ("TPM13", "financial", "Position flows (display report)"),
            ("FB03", "financial", "Accounting document if a flow posted"),
            ("FBL3N", "financial", "G/L line for the house-bank account"),
        ],
    },
    "quality": {
        "title": "Quality (your words)",
        "spine": "material → inspection setup → lot → usage decision → stock",
        "story": "Quality sits between receipt and usable stock. If inspection is on, goods receipt is not the end — the lot is.",
        "hops": ["Material QM view → inspection lot → UD → unrestricted or blocked"],
        "questions": ["Is QM in procurement on?", "Are lots open?", "Does UD block the next PTP/OTC hop?"],
        "tcodes": [
            ("MM03", "master", "Material — look at Quality view"),
            ("SE16N", "org", "Inspection setup / lots (display table)"),
            ("QA03", "transaction", "Display inspection lot if authorized"),
            ("QA13", "transaction", "Display usage decision if authorized"),
        ],
    },
    "warehouse": {
        "title": "Warehouse / WM (your words)",
        "spine": "plant → warehouse → bin → transfer order → goods issue",
        "story": "Warehouse delay is why deliveries exist but billing does not. GI is the hinge to cash.",
        "hops": ["Delivery → warehouse task → GI → billable"],
        "questions": ["Which warehouse number?", "Are bins empty or full?", "Is GI waiting on a TO?"],
        "tcodes": [
            ("SE16N", "org", "Warehouse / bin / quant tables"),
            ("LS03N", "master", "Display storage bin if WM"),
            ("VL03N", "transaction", "Display delivery — is GI done?"),
            ("LT21", "transaction", "Display transfer order if WM"),
        ],
    },
    "maintenance": {
        "title": "Plant maintenance (your words)",
        "spine": "equipment → notification → order → confirm → settle",
        "story": "PM is a cost object story. An open order is WIP. Settlement is the hop to FI/CO.",
        "hops": ["Equipment → order → confirmation → settlement → cost center / order"],
        "questions": ["Which equipment?", "Are orders confirmed?", "Where do they settle?"],
        "tcodes": [
            ("IE03", "master", "Display equipment"),
            ("IW23", "transaction", "Display notification"),
            ("IW33", "transaction", "Display PM order"),
            ("KOB1", "financial", "Order actual line items"),
        ],
    },
    "project": {
        "title": "Project system (your words)",
        "spine": "project → WBS → network / order → actuals → settle",
        "story": "This client had zero project stock. If you name PS, first prove a project exists before designing stock-on-WBS.",
        "hops": ["Project → WBS → actuals → settlement"],
        "questions": ["Is there a project?", "Is stock project-stock or ordinary?"],
        "tcodes": [
            ("CJ03", "master", "Display project"),
            ("CJ13", "master", "Display WBS"),
            ("CN43N", "transaction", "Project info if authorized"),
            ("CJI3", "financial", "Project actuals"),
        ],
    },
    "production": {
        "title": "Production (your words)",
        "spine": "material → BOM/routing → order → confirm → receive → cost",
        "story": "Shop floor is live here. Unconfirmed orders are WIP, not variance. Do not redesign costing until open orders are confirmed or closed.",
        "hops": ["Order → confirmation → goods receipt to stock → variance"],
        "questions": ["How many orders unconfirmed?", "Do reservations hit stock or drop-ship materials?"],
        "tcodes": [
            ("MM03", "master", "Material"),
            ("CO03", "transaction", "Display production order"),
            ("CK13N", "transaction", "Display cost estimate"),
            ("CKM3N", "financial", "Material price analysis"),
        ],
    },
    "intercompany": {
        "title": "Intercompany (your words)",
        "spine": "selling company → buying company → STO or IC invoice → elimination",
        "story": "Stock transport 100011 already exists as a plant-to-plant move. Intercompany billing is a different economy than third-party drop-ship. Do not mix them.",
        "hops": ["STO → GI supplying plant → GR receiving plant → IC invoice"],
        "questions": ["Same company or two companies?", "Is there markup?", "Does elimination exist at close?"],
        "tcodes": [
            ("ME23N", "transaction", "Display STO / PO"),
            ("VL03N", "transaction", "Display delivery if used"),
            ("VF03", "transaction", "Display IC billing if used"),
            ("FB03", "financial", "FI document"),
        ],
    },
    "credit": {
        "title": "Credit (your words)",
        "spine": "customer → limit → order check → block → release",
        "story": "Classic credit master was empty on this book. 12k orders with no limit is a decision, not a missing t-code.",
        "hops": ["Order → credit check → VKM1 block → release → delivery"],
        "questions": ["Classic or FSCM?", "Empty on purpose?", "Who releases blocks?"],
        "tcodes": [
            ("XD03", "master", "Display customer"),
            ("FD33", "master", "Display credit — never FD32 from this wing"),
            ("VA03", "transaction", "Display sales order — was it blocked?"),
            ("FBL5N", "financial", "Open items vs any limit"),
        ],
    },
    "tax": {
        "title": "Tax / e-document (your words)",
        "spine": "org → tax code → document → reporting / e-invoice",
        "story": "Tax is a hop on every invoice. A posted bill with the wrong tax code is a cash and compliance problem, not an SD-only problem.",
        "hops": ["Customer tax → invoice tax → FI tax line → return"],
        "questions": ["Which country?", "eDocument or classic?", "Do invoices post with tax?"],
        "tcodes": [
            ("XD03", "master", "Customer tax view"),
            ("VF03", "transaction", "Display billing — tax"),
            ("FB03", "financial", "FI tax lines"),
            ("SE16N", "org", "Tax codes / eDocument tables"),
        ],
    },
    "hr": {
        "title": "HR / payroll (your words)",
        "spine": "org → person → infotype → payroll result → FI",
        "story": "HR is people and postings. Display personnel and payroll results; do not run payroll from this wing.",
        "hops": ["Person → payroll result → FI posting"],
        "questions": ["Which personnel area?", "Have results posted to FI?"],
        "tcodes": [
            ("PA20", "master", "Display HR master"),
            ("PC_PAYRESULT", "transaction", "Payroll result display if authorized"),
            ("FB03", "financial", "FI posting from payroll"),
            ("SE16N", "org", "Org / infotype tables"),
        ],
    },
}


def _norm(text: str) -> str:
    return " ".join((text or "").strip().lower().replace("_", " ").replace("-", " ").split())


def _best_key(text: str, keys) -> str | None:
    """Exact or whole-token match first. Short keys like 'ar' must not steal 'rar'."""
    n = _norm(text)
    keys = list(keys)
    if n in keys:
        return n
    tokens = n.split()
    for key in sorted(keys, key=len, reverse=True):
        if key in tokens:
            return key
    for key in sorted(keys, key=len, reverse=True):
        if len(key) >= 3 and key in n:
            return key
    return None


def _match_catalog(text: str) -> str | None:
    n = _norm(text)
    if n in CYCLES:
        return n
    key = _best_key(n, _ALIASES)
    return _ALIASES.get(key) if key else None


def _match_library(text: str) -> str | None:
    return _best_key(text, _LIBRARY)


def _safe_tcode(code: str) -> str | None:
    try:
        return assert_display_tcode(code)
    except DisplayPolicyError:
        return None


def _steps_from_pairs(pairs: list[tuple[str, str, str]]) -> list[dict]:
    out = []
    for tcode, phase, purpose in pairs:
        safe = _safe_tcode(tcode)
        out.append(
            {
                "tcode": safe or tcode,
                "phase": phase,
                "purpose": purpose,
                "allowed": bool(safe),
                "note": "" if safe else "Not on the display allow-list — open SE16N instead, or we add it as display-only.",
            }
        )
    return out


def _resolve(text: str) -> tuple[str, str | None]:
    n = _norm(text)
    if n in CYCLES:
        return "catalog", n
    if n in _LIBRARY:
        return "library", n
    alias = _best_key(n, _ALIASES)
    if alias:
        dest = _ALIASES[alias]
        if dest in CYCLES:
            return "catalog", dest
        if dest in _LIBRARY:
            return "library", dest
    lib = _best_key(n, _LIBRARY)
    if lib:
        return "library", lib
    return "generic", None


def analyze_process(raw: str) -> dict:
    """Any process name → story, hops, questions, display steps."""
    name = (raw or "").strip()
    if not name:
        return {"ok": False, "error": "Name a process. Any process. Example: RAR, treasury, quality, credit."}

    kind, key = _resolve(name)
    if kind == "catalog" and key:
        c = get_cycle(key)
        steps = [
            {
                "tcode": s.tcode,
                "phase": s.phase,
                "purpose": s.purpose,
                "allowed": True,
                "note": s.notes,
            }
            for s in c.steps
        ]
        return {
            "ok": True,
            "source": "catalog-example",
            "asked": name,
            "title": c.title,
            "spine": c.spine,
            "story": f"This is a catalog example for “{c.title}”. It is not the only process this product can walk. You can name any other process in the box above.",
            "hops": [f"{s.phase}: {s.tcode} — {s.purpose}" for s in c.steps],
            "questions": [
                "What starts this process?",
                "What document proves the next hop happened?",
                "Where does cash or cost land?",
                "What unused type in the search help will create a ticket?",
            ],
            "steps": steps,
        }

    if kind == "library" and key:
        spec = _LIBRARY[key]
        return {
            "ok": True,
            "source": "library",
            "asked": name,
            "title": spec["title"],
            "spine": spec["spine"],
            "story": spec["story"],
            "hops": spec["hops"],
            "questions": spec["questions"],
            "scenarios": spec.get("scenarios") or [],
            "steps": _steps_from_pairs(spec["tcodes"]),
        }

    # Unknown process — still a product: generic display spine they can walk.
    steps = _steps_from_pairs(
        [
            ("SE16N", "org", f"Open the config / master table for “{name}” — Number of Entries, not a 500 list"),
            ("SE16N", "master", f"Open the master that this process consumes (customer, vendor, material, equipment…)"),
            ("SE16N", "transaction", f"Open the document table that proves “{name}” actually ran"),
            ("FB03", "financial", "If it posted, display the FI document — cash or cost always lands somewhere"),
        ]
    )
    return {
        "ok": True,
        "source": "generic",
        "asked": name,
        "title": f"Your process: {name}",
        "spine": "org → master → document → financial display",
        "story": (
            f"“{name}” is not a pre-built example. That is fine. The product still walks it: "
            "look at the organisation, the master, a real document, and the FI landing. "
            "Type a display t-code you use for this process in Go, or open SE16N and name the table. "
            "We never create from this wing."
        ),
        "hops": [
            "What org key starts it (company, plant, controlling area, sales area)?",
            "What master must exist?",
            "What document number proves it ran?",
            "Which FI or CO line is the money?",
        ],
        "questions": [
            f"Who starts “{name}”?",
            "What blocks the next hop?",
            "Is this the same P&L as sales and purchasing, or a side ledger?",
            "Which search-help types are unused and dangerous?",
        ],
        "steps": steps,
    }
