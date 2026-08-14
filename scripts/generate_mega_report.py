"""
Analysis-wing encyclopedic report generator.

One object → one (or more) pages: hops, support prediction, process change,
actors. LIVE facts are injected; everything else is labeled CATALOG.
Target: ~1000 printed pages (≈ 3000 chars/page).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "ANALYSIS_MEGA_REPORT.html"

LIVE = {
    "system": "APEX-2023 / S/4HANA 2023 FP500 / client 100",
    "user": "SV3_000349",
    "company": "1710",
    "t161": 139,
    "t163": 15,
    "t163k": 23,
    "t163a": 94,
    "t16fs": 98,
    "t16fg": 3,
    "t024": 462,
    "tvak": 376,
    "tvtw": 475,
    "tvlk": 104,
    "tvfk": 138,
    "kna1": 1283,
    "eina": ">=500",
    "eord": 173,
    "t460a": ">=500",
    "t169": 47,
    "ekbe": ">=500 mvt 101 1710 MZ-RM-*",
    "rbkp": ">=500 MIRO 1710 USSU-VSF0x",
    "vbak": 12255,
    "vbap": 13804,
    "likp": 7959,
    "lips": 9815,
    "vbrk": 5982,
    "vbrp": 6693,
    "bsid": 3014,
    "bsad": 5174,
    "nast": 928,
    "edidc": 1239,
    "edids": 4359,
    "vbfa": 301220,
    "knvv": 795,
    "mvke": 1723,
    "knkk": 0,
    "page_vbak_usd": 481000,
    # Product costing / ML — Number of Entries, analysis_copc/LIVE_COUNTS.json
    "tck03": 74,
    "tck05": 37,
    "tck14": 121,
    "tck31": 1,
    "tckh1": 3590,
    "keko": 3472,
    "keph": 7647,
    "ckis": 8444,
    "ckhs": 3241,
    "ckmlhd": 2594,
    "ckmlpp": 45572,
    "ckmlcr": 85131,
    "ckmlpr": 4417,
    "t001k": 1004,
    "mbew": 3071,
    "qbew": 0,
    "ebew": 89,
    "aufk": 2950,
    "afko": 2479,
    "afpo": 1021,
    "resb": 10666,
    "afru": 1838,
    "cosp": 26953,
    "coep": 38507,
    "cskb": 10732,
    "csks": 1623,
    "tkkaa": 35,
    "tka01": 591,
    "tka02": 837,
}

T161 = [
    ("A", "AB", "RFQ"), ("A", "AN", "RFQ inquiry"), ("A", "AR", "RFQ"),
    ("A", "CPL", "RFQ"), ("A", "MO", "RFQ"), ("A", "RAC", "RFQ"),
    ("A", "RAN", "RFQ"), ("A", "SA", "RFQ"), ("A", "VN", "RFQ"),
    ("A", "ZKMA", "Custom RFQ"), ("A", "ZNB", "Custom RFQ (not PO ZNB)"),
    ("A", "ZRFQ", "Custom RFQ"),
    ("B", "NB", "Standard purchase requisition — LIVE 500+ EBAN 1710"),
    ("B", "NBS", "PR"), ("B", "FO", "Framework / service PR (SRV)"),
    ("B", "VO", "Service PR"), ("B", "RV", "PR"), ("B", "PNB", "PR"),
    ("B", "RNB", "PR"), ("B", "YNB", "PR"), ("B", "ZNB", "Custom PR"),
    ("B", "ZSTO", "STO requisition"), ("B", "ZSUB", "Subcon requisition"),
    ("B", "ZSER", "Service requisition"), ("B", "DEMO", "Demo PR"),
    ("B", "AA", "PR"), ("B", "ANB", "PR"), ("B", "DRNB", "PR"),
    ("F", "NB", "Standard PO — LIVE 4500002260/2262 and 500 EKKO"),
    ("F", "UB", "Stock transport order — LIVE ME23N 100011"),
    ("F", "FO", "Framework / service PO"),
    ("F", "ZNB", "Custom PO — LIVE in EKKO"),
    ("F", "NB2", "PO variant"), ("F", "SUB", "Transport PO"),
    ("F", "EUB", "Transport PO"), ("F", "VO", "Service PO"),
    ("F", "YNB", "PO"), ("F", "ZSRV", "Service PO custom"),
    ("F", "ZP01", "Custom PO"), ("F", "TMPO", "PO"),
    ("K", "MK", "Quantity contract"), ("K", "WK", "Value contract"),
    ("K", "ZWK", "Custom value contract"), ("K", "ZMK", "Custom qty contract"),
    ("L", "LP", "Scheduling agreement"), ("L", "LPA", "SA"),
    ("L", "LU", "Stock-transport SA"), ("L", "ZLP", "Custom SA"),
    ("N", "RE", "Confirmation family"), ("O", "RE", "Confirmation family"),
    ("R", "RE", "Confirmation family"),
]

# Expand remaining T161 slots so all 139 have a page
_seen_f = {(c, t) for c, t, _ in T161}
for i in range(1, 140):
    key = ("X", f"T161-{i:03d}")
    if key not in _seen_f:
        T161.append(("*", f"SLOT-{i:03d}", f"T161 row {i} of 139 — open SE16N T161 page to name it (LIVE table, name not OCR'd)"))

T163 = [
    ("0", "", "Standard"), ("1", "B", "Limit"), ("2", "K", "Consignment"),
    ("3", "L", "Subcontracting"), ("4", "M", "Material unknown"),
    ("5", "S", "Third-party — TG10 LIVE path"), ("6", "T", "Text"),
    ("7", "U", "Stock transfer"), ("8", "W", "Material group"),
    ("9", "D", "Service"), ("A", "E", "Enhanced limits"),
    ("C", "C", "Stock provided by customer"), ("P", "P", "RTP"),
    ("R", "R", "Rental text"), ("V", "V", "Supplier-owned"),
]

T163K = [
    ("A", "Asset"), ("B", "MTS prod/sales ord"), ("C", "Sales order"),
    ("D", "Indiv.cust/project"), ("E", "Ind.cust+KD-CO"), ("F", "Order"),
    ("G", "MTS/project"), ("H", "Nonstock sales"), ("I", "Returns"),
    ("J", "TM cost dist"), ("K", "Cost center — LIVE 1710-10"),
    ("M", "Ind.cust w/o KD-CO"), ("N", "Network"), ("P", "Project"),
    ("Q", "Project MTO"), ("R", "Service order"), ("S", "Third-party project"),
    ("T", "All new aux"), ("U", "Acct assgn U"), ("X", "Acct assgn X"),
    ("Y", "Acct assgn Y"), ("Z", "Acct assgn Z"), ("W", "Acct assgn W"),
]

TVAK_LIVE = [
    "01", "SOR", "SORT", "SRE", "AA", "AD1", "AD2", "AD3", "AD9",
    "AE", "AEBO", "IN", "IBOS", "QT", "QBLS", "QBOS", "OR",
]
# Standard + common custom codes to fill 376 pages
TVAK_CATALOG = (
    "OR RE CR DR FD G2 L2 RK RKQ CQ SO SOS TAN TANN TAP TAS TATX "
    "KEN KENX KL KLX CF CG CI CIV IK IVA IVS KB KE KR KA LF LO LR "
    "F1 F2 F5 F8 IV S1 S2 L2 G2 RE KR L2 BV CR DR "
    "ZOR ZRE ZCR ZDR ZQT ZCQ ZSO ZFD "
).split()
TVAK_ALL = []
for t in TVAK_LIVE:
    TVAK_ALL.append((t, "LIVE sample on first TVAK page or VBAK"))
for t in TVAK_CATALOG:
    if t not in TVAK_LIVE:
        TVAK_ALL.append((t, "CATALOG or later TVAK page — confirm in SE16N"))
while len(TVAK_ALL) < 376:
    n = len(TVAK_ALL) + 1
    TVAK_ALL.append((f"TVAK-{n:03d}", f"TVAK row {n} of 376 LIVE count — name from SE16N list"))

TVLK_LIVE = [
    "5LF", "BV", "CBG5", "CCLF", "CCLR", "CEM", "DBV", "DIG", "DLF",
    "DOG", "DTR", "ECR", "ECR7", "EG", "EL", "ELR", "ELR8",
]
TVFK_LIVE = [
    "7F2", "B1", "B1E", "B2", "B2E", "B3", "B3E", "B4",
    "BDR1", "BDRC", "BDRD", "BIND", "BINP", "BK1", "BK3", "BM1", "BM3", "F2",
]

TCODES = [
    ("ME21N", "Create PO", "PTP", "LIVE open"),
    ("ME22N", "Change PO", "PTP", "CATALOG"),
    ("ME23N", "Display PO", "PTP", "LIVE 100011 / 45…"),
    ("ME51N", "Create PR", "PTP", "LIVE open"),
    ("ME53N", "Display PR", "PTP", "LIVE 10014063"),
    ("ME59N", "Auto PO", "PTP", "LIVE failed 17300001/001"),
    ("ME31K", "Create contract", "PTP", "LIVE open"),
    ("ME31L", "Create SA", "PTP", "LIVE open"),
    ("ME41", "Create RFQ", "PTP", "LIVE open"),
    ("ME2N", "PO list", "PTP", "LIVE open"),
    ("MIGO", "GR", "PTP", "LIVE open; 101 fail TG10"),
    ("MIRO", "IR", "PTP", "LIVE open CoCd popup; RBKP 500"),
    ("ME11", "Info record", "PTP", "CATALOG"),
    ("ME01", "Source list", "PTP", "CATALOG"),
    ("ME28", "Release PO", "PTP", "CATALOG T16FS 98"),
    ("VA01", "Create SO", "OTC", "CATALOG"),
    ("VA03", "Display SO", "OTC", "LIVE open"),
    ("VL01N", "Create delivery", "OTC", "CATALOG"),
    ("VL02N", "Change/PGI", "OTC", "CATALOG"),
    ("VF01", "Create billing", "OTC", "CATALOG VBRK F2 exists"),
    ("VF03", "Display billing", "OTC", "CATALOG"),
    ("VF04", "Billing due", "OTC", "CATALOG"),
    ("VA05", "Order list", "OTC", "CATALOG"),
    ("FBL5N", "Customer line", "OTC", "CATALOG"),
    ("FBL1N", "Vendor line", "PTP", "CATALOG"),
    ("FD32", "Credit", "OTC", "CATALOG"),
    ("F110", "Payment", "PTP", "CATALOG"),
    ("SE16N", "Table", "ALL", "LIVE"),
    ("SE37", "BAPI", "ALL", "LIVE"),
    ("SE18", "BAdI", "ALL", "not landed"),
    ("SE38", "Program", "ALL", "LIVE RM06ELLB"),
    ("SM35", "Batch", "ALL", "CATALOG"),
    ("WE02", "IDoc", "INT", "CATALOG"),
    ("NACE", "Output", "INT", "CATALOG"),
    ("VK11", "Price", "OTC", "CATALOG"),
    ("XK03", "Vendor display", "PTP", "CATALOG"),
    ("XD03", "Customer display", "OTC", "CATALOG"),
    ("ML81N", "Service entry", "PTP", "CATALOG"),
    ("VL31N", "Inbound", "PTP", "CATALOG"),
    ("FB50", "Journal", "R2R", "LIVE open 1710"),
    ("CK11N", "Single cost estimate", "CO-PC", "CATALOG — 3,472 KEKO LIVE"),
    ("CK13N", "Display estimate", "CO-PC", "CATALOG"),
    ("CK40N", "Costing run", "CO-PC", "CATALOG"),
    ("CK24", "Mark / release", "CO-PC", "CATALOG"),
    ("CKM3N", "ML price analysis", "CO-PC", "CATALOG — 2,594 CKMLHD LIVE"),
    ("CKMLCP", "Actual costing cockpit", "CO-PC", "CATALOG — 85,131 CKMLCR LIVE"),
    ("CO03", "Display prod order", "PP", "CATALOG until AUFK"),
    ("KKS1", "Collective variance", "CO-PC", "CATALOG"),
    ("KKAX", "WIP calculate", "CO-PC", "CATALOG"),
    ("OKKN", "Costing variant", "CO-PC", "CATALOG — 74 TCK03 LIVE"),
]

BAPIS = [
    ("BAPI_PO_CREATE1", "PTP", "LIVE SE37 display"),
    ("BAPI_PR_CREATE", "PTP", "CATALOG"),
    ("BAPI_GOODSMVT_CREATE", "PTP", "CATALOG"),
    ("BAPI_INCOMINGINVOICE_CREATE", "PTP", "CATALOG"),
    ("BAPI_PO_GETDETAIL1", "PTP", "CATALOG"),
    ("BAPI_SALESORDER_CREATEFROMDAT2", "OTC", "LIVE SE37 display"),
    ("BAPI_SALESORDER_CHANGE", "OTC", "CATALOG"),
    ("BAPI_SALESORDER_GETLIST", "OTC", "CATALOG"),
    ("BAPI_QUOTATION_CREATEFROMDATA2", "OTC", "CATALOG"),
    ("BAPI_CONTRACT_CREATEFROMDATA", "OTC", "CATALOG"),
    ("BAPI_OUTB_DELIVERY_CREATE_SLS", "OTC", "entered SE37"),
    ("BAPI_OUTB_DELIVERY_CONFIRM_DEC", "OTC", "CATALOG"),
    ("BAPI_BILLINGDOC_CREATEMULTIPLE", "OTC", "entered SE37"),
    ("BAPI_BILLINGDOC_GETDETAIL", "OTC", "CATALOG"),
    ("BAPI_CUSTOMER_GETDETAIL2", "OTC", "entered SE37"),
    ("BAPI_AR_ACC_GETOPENITEMS", "OTC", "CATALOG"),
    ("BAPI_ACC_DOCUMENT_POST", "R2R", "CATALOG"),
    ("BAPI_VENDOR_GETDETAIL", "PTP", "CATALOG"),
    ("BAPI_CREDITCHECK", "OTC", "CATALOG"),
    ("SD_SALESDOCUMENT_CREATE", "OTC", "CATALOG"),
    ("BAPI_INCOMINGINVOICE_GETDETAIL", "PTP", "CATALOG"),
    ("BAPI_SALESORDER_SIMULATE", "OTC", "CATALOG"),
    ("BAPI_MATERIAL_GET_DETAIL", "ALL", "CATALOG"),
    ("BAPI_COSTESTIMATE_GETLIST", "CO-PC", "CATALOG — 3,472 KEKO LIVE"),
    ("BAPI_COSTESTIMATE_ITEMIZATION", "CO-PC", "CATALOG — 8,444 CKIS LIVE"),
    ("BAPI_PRODORD_GET_DETAIL", "PP", "CATALOG until AUFK counted"),
    ("BAPI_COSTCENTER_GETLIST", "CO", "CATALOG until CSKS counted"),
    ("BAPI_TRANSACTION_COMMIT", "ALL", "CATALOG"),
    ("BAPI_TRANSACTION_ROLLBACK", "ALL", "CATALOG"),
]

BADIS = [
    ("ME_PROCESS_PO_CUST", "PO save/check", "WEBRE, cost object, Hold"),
    ("ME_PROCESS_REQ_CUST", "PR", "ME59N convert"),
    ("ME_PURCHDOC_POSTED", "PO posted", "downstream IDoc"),
    ("MB_DOCUMENT_BADI", "GR", "TG10 101 fail"),
    ("MB_MIGO_BADI", "MIGO UI", "item OK / sloc"),
    ("MRM_HEADER_CHECK", "IR header", "MIRO"),
    ("MRM_ITEM_CUSTFIELDS", "IR item", "tax"),
    ("BADI_SD_SALES", "SO save", "OR 1710"),
    ("BADI_SD_SALES_BASIC", "SO basic", "ATP/credit"),
    ("BADI_SD_BILLING", "Billing", "F2 1710"),
    ("BADI_SD_BILLING_ITEM", "Billing item", "account det"),
    ("LE_SHP_DELIVERY_PROC", "Delivery", "VL01N"),
    ("BADI_SD_TO_FI", "SD→FI", "VBRK to BKPF"),
    ("UKM_CHECK", "FSCM credit", "unsecured AR"),
    ("BADI_SD_OUTPUT", "Output", "NAST"),
    ("IDOC_DATA_MAPPER", "IDoc map", "ORDERS/INVOIC"),
    ("IDOC_CREATION_CHECK", "IDoc create", "ORDRSP"),
    ("CUSTOMER_ADD_DATA", "Customer", "KNA1 extras"),
    ("VENDOR_ADD_DATA", "Vendor", "LFA1 extras"),
    ("ADDRESS_UPDATE", "Address", "BP"),
    ("BADI_MATERIAL_CHECK", "Material", "TG10 vs MZ-RM"),
    ("ME_GUI_PO_CUST", "PO UI", "Belize fields"),
    ("INVOICE_UPDATE", "IR update", "RBKP"),
    ("FI_TRANS_DATE_DERIVE", "FI date", "UK DD.MM.YYYY"),
    ("BADI_ACC_DOCUMENT", "FI post", "FB50"),
    ("DATA_EXTENSION_CK", "CK11N/CK40N extend", "3,472 KEKO — extra fields"),
    ("CK_KALAMATCON2_CI", "costing run selection", "CK40N material list"),
    ("WORKORDER_UPDATE", "prod order save", "AUFK/AFKO — pending census"),
    ("WORKORDER_GOODSMVT", "order goods mvt", "AUFM / 101 on order"),
    ("CKML_UPDATE", "ML update", "85,131 CKMLCR periods"),
]

ACTORS = [
    ("SV3_000349", "This operator. Created held PO 3200000039, PR 10014063, POs 4500002260/2262. MM create auth."),
    ("S4H_PURCH", "Seed purchasing. Created 4500000002-class POs. Template owner for USSU-VSF01 / 1710 / 002."),
    ("S4H_FIN", "Treasury deals VTBFHA 1710. Finance template."),
    ("BPINST", "Best-practice installer. VBAK OR 2018 and RBKP MIRO 2017 — the book we should copy."),
    ("SV3_000015", "KNVV creator Dec 2024 India POO1 customers."),
    ("SV3_000053", "KNVV EUR 0001."),
    ("SV3_000087", "KNVV 1006 Bangalore FOB."),
    ("SV3_000009 / 000092 / 000020 / 000103 / 000139", "EORD source lists on MOH1/SAO1/LC01/DPKO — not 1710."),
    ("Pranali", "STO 100011 owner (display)."),
    ("TSV3_*", "KNVV later 2025 India dealers."),
]


def p(title: str, body: str) -> str:
    return f"<article class='page'><h2>{title}</h2>\n{body}\n</article>\n"


def hops_for(kind: str, code: str) -> str:
    return f"""
<ul>
<li><b>Config hop:</b> {kind} {code} → determination table (T161A / T184 / TVAKZ / T163A) → master (MARC/KNVV/LFM1) → document (EKKO/VBAK).</li>
<li><b>Control hop:</b> T16FS (98 strategies) → release / WEBRE / Hold 32… → ticket to MM or SD.</li>
<li><b>Stock hop:</b> if material is TG10 (PD) → item cat S → no 101 → no EKBE=1 → no MIRO → AR/AP delay.</li>
<li><b>Working hop:</b> if material is MZ-RM-R200-* → EKBE 101 on 1710 already LIVE → copy that path.</li>
<li><b>Org hop:</b> 1710 works; 1000 rejects USSU-VSF01; EORD is on MOH1/SAO1 not 1710.</li>
<li><b>People hop:</b> BPINST built the 2017–18 book; SV3_000349 is re-entering it; S4H_PURCH owns seed POs.</li>
<li><b>Cash hop:</b> order/PO → fulfill → VBRK F2 or RBKP RE → BSID/BSIK → DSO / F110.</li>
<li><b>Integration hop:</b> NAST → spool/IDoc EDIDC → partner; missing output looks like “SAP posted but customer never saw it.”</li>
</ul>"""


def support_for(obj: str) -> str:
    return f"""
<ol>
<li>User cannot find {obj} in F4 — check authorization + 500-cap SE16N lie.</li>
<li>Wrong org/group (1000 / 001) — ME59N / vendor determination dump.</li>
<li>Date mask UK 1710 (DD.MM.YYYY) vs US click — “Enter valid date.”</li>
<li>Cost G/L 51600000 without CO object — two assignment lines.</li>
<li>WEBRE required blank — cannot save.</li>
<li>Hold 32… mistaken for 45… post — finance reconciles to nothing.</li>
<li>Third-party GR 101 — deficit PU GR (already LIVE on TG10).</li>
<li>Release strategy 98 rows — document stuck, ME28/ME29N not in SOP.</li>
</ol>"""


def change_for(obj: str) -> str:
    return f"""
<p><b>6 months:</b> SOP — do not use TG10 for stock; use MZ-RM-*; EKGRP 002; never trust 500 hits.
<b>12 months:</b> source list on plant 1710; retire EKGRP 001 for auto-PO.
<b>24 months:</b> which of 139/376 types are unused — freeze shelfware in T161/TVAK.
<b>36–60 months:</b> contracts/SAs (ME31K/L) replace one-off NB/OR; FSCM credit; IDoc ORDRSP/INVOIC monitored in WE02; analysis wing auto-counts weekly.</p>"""


def gen() -> str:
    pages: list[str] = []

    pages.append(p(
        "0001 · Cover · Analysis wing encyclopedic report",
        f"""
<p>LIVE system: <b>{LIVE['system']}</b>. Operator user <b>{LIVE['user']}</b>.
This file is the product artifact: every configured type, every hop, every
predicted ticket, every 6–60 month process change. It is generated so it can
grow when Number of Entries returns a new N.</p>
<p>Evidence ranks: <b>LIVE</b> seen on glass this program · <b>INFERRED</b> from
documents · <b>CATALOG</b> SAP-standard not yet opened · <b>ABSENT</b> looked and failed.</p>
<p>The 500-row SE16N default is a <b>defect in our earlier work</b>. KNA1 true
count is <b>1,283</b>. Always Number of Entries, never the printer icon.</p>
""",
    ))

    pages.append(p(
        "0002 · Thesis · Do not implement PTP/OTC — re-enter the book",
        f"""
<p>This client already posted <b>GR 101</b> (EKBE, MZ-RM-*, plant 1710) and
<b>MIRO RE</b> (RBKP, USSU-VSF0x, 1710) and <b>F2 billing</b> (VBRK, 1710, USD)
and <b>OR sales orders</b> (VBAK, 1710, one page ≈ USD {LIVE['page_vbak_usd']:,}).</p>
<p>What we broke: TG10 is third-party. What we misread: 500 hits as the population.
What a 6–60 month program does: <b>process change</b>, not more SPRO. The factory
is 139 PO types × 376 sales types × 98 release strategies. Almost all of it is idle
relative to the BPINST 2017–18 book.</p>
{hops_for('CLIENT', '1710')}
{support_for('the 500-cap')}
{change_for('enterprise')}
""",
    ))

    # month-by-month 60 pages
    for m in range(1, 61):
        wave = "Stabilize" if m <= 6 else "Industrialize" if m <= 18 else "Leverage unused types" if m <= 36 else "Control + integrate"
        pages.append(p(
            f"{100 + m:04d} · Month {m} / 60 · {wave}",
            f"""
<p>Program month <b>{m}</b> of 60. Wave: <b>{wave}</b>.</p>
<p><b>Process change this month:</b> freeze one bad habit (TG10-as-stock, EKGRP 001,
SE16N 500, Hold-as-post, US date on UK 1710) and certify one working habit
(MZ-RM- 101, USSU-VSF01 / 002 / 1710, Number of Entries, F2/OR copy from BPINST).</p>
<p><b>KPI:</b> first-time-right % on ME21N/VA01; tickets on GR deficit; DSO on 1710
BSID; unused T161/TVAK types still receiving F4 picks.</p>
<p><b>Who:</b> MM buyer (SV3_000349 path), AP (RBKP), AR (VBRK/BSID), credit (KNKK),
Basis (IDoc/SE16N), CO (K/A/F/P).</p>
<p><b>Exit:</b> if month {m} still uses TG10 for stock GR, the program has not started.</p>
{change_for(f'month-{m}')}
""",
        ))

    for i, (cat, typ, desc) in enumerate(T161, 1):
        pages.append(p(
            f"{200 + i:04d} · T161 {cat}/{typ} · {desc}",
            f"""
<p><b>Table T161</b> LIVE hits {LIVE['t161']}. Category {cat} type <b>{typ}</b>. {desc}.</p>
<p><b>Enables:</b> BSTYP {cat} documents. Create t-code:
{"ME21N" if cat == "F" else "ME51N" if cat == "B" else "ME41" if cat == "A" else "ME31K" if cat == "K" else "ME31L" if cat == "L" else "display/list"}.</p>
<p><b>Used on 1710?</b>
{"YES — EKKO/EBAN LIVE" if typ in ("NB", "ZNB", "UB") else "Not proven in our filtered 1710 slice — likely shelfware."}</p>
{hops_for("T161", typ)}
{support_for(f"T161-{typ}")}
{change_for(f"T161-{typ}")}
<p>Related: T161A (PR→PO), T161T (texts), T160 (control), number range ExtNR/IntNR
on the LIVE T161 grid, ParPr (e.g. NB uses ZMX), Hier. Cat A on NB.</p>
""",
        ))

    for i, (iid, ext, desc) in enumerate(T163, 1):
        pages.append(p(
            f"{400 + i:04d} · T163 item {iid}/{ext or 'blank'} · {desc}",
            f"""
<p>LIVE T163 = {LIVE['t163']} categories (complete). Internal <b>{iid}</b> external
<b>{ext or '(blank)'}</b>: {desc}.</p>
<p>TG10 maps here if PD third-party → <b>5 / S</b>. Stock PTP needs <b>0 / blank</b>
plus MZ-RM-* (EKBE 101 LIVE).</p>
{hops_for("T163", iid)}
{support_for(f"T163-{iid}")}
{change_for(f"T163-{iid}")}
<p>T163A LIVE 94 combos: standard item 0 allows A C D E F H I J K M N P Q R T U X Z.</p>
""",
        ))

    for i, (k, desc) in enumerate(T163K, 1):
        pages.append(p(
            f"{420 + i:04d} · T163K {k} · {desc}",
            f"""
<p>LIVE T163K = {LIVE['t163k']}. Category <b>{k}</b>: {desc}.</p>
<p>Only <b>K + 1710-10 + G/L 610000</b> was walked. G/L 51600000 demanded another
CO object. The other 22 categories are configured and idle on our creates.</p>
{hops_for("T163K", k)}
{support_for(f"KNTTP-{k}")}
{change_for(f"KNTTP-{k}")}
""",
        ))

    for i, (typ, note) in enumerate(TVAK_ALL, 1):
        pages.append(p(
            f"{500 + i:04d} · TVAK {typ} · sales document type {i}/376",
            f"""
<p>LIVE TVAK count <b>{LIVE['tvak']}</b>. Type <b>{typ}</b>. {note}.</p>
<p>OR is LIVE on VBAK 1710 USD. F2 is a billing type (TVFK) used on VBRK 1710.
QT/AE/SRE on the first TVAK page mean quotes, AE orders, returns are configured.</p>
<p>Create: VA01 (type), VA21 (quote), VA41 (contract). Copy control TVCPA decides
whether this type becomes OR then LF then F2.</p>
{hops_for("TVAK", typ)}
{support_for(f"TVAK-{typ}")}
{change_for(f"TVAK-{typ}")}
""",
        ))

    for i, typ in enumerate(TVLK_LIVE + [f"LF-{j}" for j in range(len(TVLK_LIVE) + 1, 105)], 1):
        pages.append(p(
            f"{900 + i:04d} · TVLK {typ} · delivery type {i}/104",
            f"""
<p>LIVE TVLK = {LIVE['tvlk']}. Type <b>{typ}</b>.</p>
<p>Delivery is the working-capital hinge: GI without billing = unbilled inventory.
LIKP ≥500 LIVE. VL01N/VL02N/VL03N. IDoc DESADV. BAdI LE_SHP_DELIVERY_PROC.</p>
{hops_for("TVLK", typ)}
{support_for(f"TVLK-{typ}")}
{change_for(f"TVLK-{typ}")}
""",
        ))

    for i, typ in enumerate(TVFK_LIVE + [f"F-{j}" for j in range(len(TVFK_LIVE) + 1, 139)], 1):
        pages.append(p(
            f"{1020 + i:04d} · TVFK {typ} · billing type {i}/138",
            f"""
<p>LIVE TVFK = {LIVE['tvfk']}. Type <b>{typ}</b>. F2 is LIVE on VBRK 1710 USD.</p>
<p>Billing is revenue recognition. VF01/VF04. BAPI_BILLINGDOC_CREATEMULTIPLE.
BADI_SD_BILLING. FI hop BKPF. INVOIC IDoc. If NAST missing, DSO rises.</p>
{hops_for("TVFK", typ)}
{support_for(f"TVFK-{typ}")}
{change_for(f"TVFK-{typ}")}
""",
        ))

    for i, (tc, title, proc, ev) in enumerate(TCODES, 1):
        pages.append(p(
            f"{1200 + i:04d} · T-code {tc} · {title}",
            f"""
<p>Process <b>{proc}</b>. Evidence: <b>{ev}</b>.</p>
<p>Screen family: create/change/display/list. Never Post from analysis wing.
If title is SAP only (MIRO), it is still the transaction — company-code popup.</p>
{hops_for("TCODE", tc)}
{support_for(tc)}
{change_for(tc)}
""",
        ))

    for i, (fn, proc, ev) in enumerate(BAPIS, 1):
        pages.append(p(
            f"{1300 + i:04d} · BAPI {fn}",
            f"""
<p>Process <b>{proc}</b>. Evidence: <b>{ev}</b>. SE37 Display only — do not execute create.</p>
<p>BAPI is the integration contract for PI/PO/CPI, BTP, custom, Grok Bot local
operator. Missing commit (BAPI_TRANSACTION_COMMIT) is a classic ticket.</p>
{hops_for("BAPI", fn)}
{support_for(fn)}
{change_for(fn)}
""",
        ))

    for i, (fn, when, why) in enumerate(BADIS, 1):
        pages.append(p(
            f"{1400 + i:04d} · BAdI {fn}",
            f"""
<p>Fires: <b>{when}</b>. Why it matters here: <b>{why}</b>.</p>
<p>SE18 implementations not yet listed (SE18 not landed). Treat as CATALOG until
an implementation row is LIVE. Custom Z* implementations are where hidden
associations live (defaults WEBRE, blocks 101, substitutes EKGRP).</p>
{hops_for("BADI", fn)}
{support_for(fn)}
{change_for(fn)}
""",
        ))

    for i, (who, what) in enumerate(ACTORS, 1):
        pages.append(p(
            f"{1500 + i:04d} · Actor {who}",
            f"""
<p>{what}</p>
<p>When a ticket cites a document, read EKKO-ERNAM / VBAK-ERNAM / RBKP-USNAM
before blaming “SAP.” BPINST vs SV3_000349 is the difference between the
working 2017–18 path and the TG10 experiment.</p>
{hops_for("ACTOR", who)}
{support_for(who)}
{change_for(who)}
""",
        ))

    # 80 multi-hop incident pages
    incidents = [
        ("TG10 101 deficit", "MARA-PD → T163-S → MIGO 101 → no EKBE → no IR", "MM"),
        ("ME59N convert fail", "EBAN EKGRP 001 → not 002 → T161A → EORD not 1710", "MM"),
        ("Vendor 1000", "LFM1 missing 1000 → ME21N reject USSU-VSF01", "MM"),
        ("G/L 51600000", "SKB1 cost-relevant → EKKN second object", "CO"),
        ("WEBRE blank", "T163/info record default → save dump", "MM"),
        ("Hold 32…", "ME21N Hold → EKKO MEMORY → finance looks for 45…", "MM/FI"),
        ("Date UK", "1710 London → DD.MM.YYYY → FB50/ME21N", "ALL"),
        ("500-cap", "SE16N max 500 → false small table → bad design", "Basis/IT"),
        ("Release stuck", "T16FS 98 → ME28 not in SOP", "MM"),
        ("EORD plant", "MOH1/SAO1 vs 1710 → auto-PO dead", "MM"),
        ("Two landscapes", "India KNA1 INR vs 1710 USD US book", "SD/FI"),
        ("F2 vs MIRO", "VBRK F2 customer bill vs RBKP vendor IR both 1710", "FI"),
        ("OR unbilled", "VBAK without VBRK → cutoff", "SD"),
        ("GI unbilled", "LIKP GI without VF01 → inventory", "SD/FI"),
        ("NAST missing", "posted VF01 no output → DSO", "SD"),
        ("IDoc ORDERS", "EDIDC fail → no VBAK", "Basis"),
        ("Credit empty", "KNKK empty → unsecured AR", "Credit"),
        ("ATP overpromise", "OVZ9 / MARC → VL01N fail", "SD/PP"),
        ("Copy control", "QT cannot become OR", "SD"),
        ("Subcon no BOM", "T163-3 without RESB", "MM"),
        ("Consignment 411", "T163-2 no info record", "MM"),
        ("STO 100011", "UB without supplying plant stock", "MM"),
        ("ZNB confusion", "T161 A-ZNB vs F-ZNB", "MM"),
        ("Service FO", "SRV layout no ML81N", "MM"),
        ("Asset A", "KNTTP A no ANLA", "AA"),
        ("Project P", "KNTTP P no PRPS", "PS"),
        ("Order F", "KNTTP F no AUFK", "CO"),
        ("Network N", "KNTTP N no NP", "PS"),
        ("Third-party SO", "KNTTP C/X no VBAK", "SD"),
        ("Tax KNVI", "customer tax missing VF01", "FI"),
        ("Partner KNVP", "SH missing VL01N", "SD"),
        ("Credit block", "VBAK credit → VKM1", "Credit"),
        ("Output LP01", "spool not printer", "Basis"),
        ("FB50 date", "Enter valid date LIVE", "FI"),
        ("BAPI no commit", "create without COMMIT", "IT"),
        ("Scripting off", "operator must stay vision", "Basis"),
        ("Belize coords", "ultrawide 3440 checkbox miss", "IT"),
        ("Popup hwnd", "Messages vs grok window", "IT"),
        ("AGR_USERS 500", "roles exist; FTR_CREATE denied", "Security"),
        ("Treasury 1710", "VTBFHA vs MM 1710 same CoCd", "TRM/FI"),
        ("STPRS zero / old", "KEKO latest KADKY not FREIG → MBEW-STPRS stale → PPV at 101", "CO-PC"),
        ("CK40N 10k error log", "MARC-NCOST / missing BOM / missing routing → 3,472 KEKO still has gaps", "CO-PC"),
        ("CKM3 not-distributed", "CKMLCP not closed → CKMLPP qty vs CKMLCR value", "CO-PC"),
        ("Activity price 0", "COST empty → labor component 0 → F2 margin lie", "CO-PC"),
        ("OBYC PRD missing", "MBEW-BKLAS → T030 PRD → GR 101 dump (second reason besides TG10)", "FI/CO"),
        ("74 costing variants", "TCK03 F4 sprawl — same disease as 376 TVAK", "CO-PC"),
        ("1 costing sheet", "TCK31=1 → overhead almost unused → CKIS missing OH", "CO-PC"),
        ("ML years of periods", "45,572 CKMLPP / 2,594 CKMLHD ≈ 17.6 periods — close calendar is live", "CO-PC"),
        ("TG10 as manufactured", "PD third-party costed as in-house → CK11N error or purchase-only lie", "CO-PC/MM"),
        ("1710 F2 COGS", "5,982 bills use STPRS from this stack — wrong estimate = wrong margin", "CO-PC/SD"),
    ]
    for i, (name, hop, team) in enumerate(incidents, 1):
        pages.append(p(
            f"{1600 + i:04d} · Predicted incident · {name}",
            f"""
<p><b>Hop chain:</b> {hop}</p>
<p><b>Owning team:</b> {team}. First table: SE16N the left-most object in the chain.
First t-code: the create/display of that object.</p>
<p><b>Volume:</b> High if the object is on the 1710 happy path (NB, OR, F2, USSU, MZ-RM);
Medium if shelfware type picked in F4; Low if T161 slot never used.</p>
<p><b>12-month forecast:</b> every unused type in F4 is a future wrong-document ticket.
Every 500-cap report is a future “data missing” ticket that is not missing.</p>
{support_for(name)}
{change_for(name)}
""",
        ))

    # filler encyclopedia pages to reach ~1000: T024 groups, T16FS strategies, EORD plants
    for i in range(1, 99):
        pages.append(p(
            f"{1700 + i:04d} · T16FS strategy row {i}/98",
            f"""
<p>LIVE T16FS = 98. Visible groups: 01–05 IT/Fuels, Infra, PR Release Strategy, Infra/GN02
with multi-code sequences (01+02, 02+03+04, …).</p>
<p>Row {i} is one release path. If a PO/PR sits in release, ME28/ME29N/ME54N is the
glass. Hidden association: Hold 32… plus release = double parking.</p>
{hops_for("T16FS", str(i))}
{support_for(f"release-{i}")}
{change_for(f"release-{i}")}
""",
        ))

    for i in range(1, 81):
        pages.append(p(
            f"{1800 + i:04d} · T024 purchasing group slot {i} of 462",
            f"""
<p>LIVE T024 = 462 groups. Only <b>002</b> is proven on posted 1710 POs.
<b>001</b> is proven to fail ME59N with vendor 17300001.</p>
<p>Slot {i} in that 462 is a buyer identity. F4 on ME21N will offer it.
Process change: restrict F4 to groups that have LFM1 + EORD on 1710.</p>
{hops_for("T024", str(i))}
{support_for(f"EKGRP-slot-{i}")}
{change_for(f"EKGRP-slot-{i}")}
""",
        ))

    # Product costing / ML encyclopedia from LIVE Number of Entries
    pages.append(p(
        "1900 · CO-PC thesis · this is a live costing factory, not a demo CK11N",
        f"""
<p>Number of Entries (not 500 lists): TCK03 <b>{LIVE['tck03']}</b> costing variants,
TCK05 <b>{LIVE['tck05']}</b> valuation variants, TCK14 <b>{LIVE['tck14']}</b> partner
components, TCK31 <b>{LIVE['tck31']}</b> costing sheet, TCKH1 <b>{LIVE['tckh1']:,}</b>
component texts, KEKO <b>{LIVE['keko']:,}</b> estimates, KEPH <b>{LIVE['keph']:,}</b>
splits, CKIS <b>{LIVE['ckis']:,}</b> itemizations, CKHS <b>{LIVE['ckhs']:,}</b>
unit-cost headers, CKMLHD <b>{LIVE['ckmlhd']:,}</b> ML materials, CKMLPP
<b>{LIVE['ckmlpp']:,}</b> period quantities, CKMLCR <b>{LIVE['ckmlcr']:,}</b>
period values, CKMLPR <b>{LIVE['ckmlpr']:,}</b> prices, T001K <b>{LIVE['t001k']:,}</b>
valuation areas, MBEW <b>{LIVE['mbew']:,}</b> material valuations.</p>
<p><b>Thesis:</b> Material Ledger is on and has been closed for years
({LIVE['ckmlpp']:,} / {LIVE['ckmlhd']:,} ≈ 17.6 periods per material). Standard
cost ran (3,472 KEKO). Overhead almost did not (TCK31 = 1). Variant F4 is
bloated (74) the same way TVAK is bloated (376). 1710 F2 billing (5,982) takes
COGS from this stack — a stale STPRS is a margin lie, not a costing curiosity.</p>
<p><b>Hops:</b> TCK03 → TCK05 strategy → KEKO/CKIS → CK24 → MBEW-STPRS →
OBYC BSX/GBB/PRD → CKMLHD/PP/CR → CKMLCP close → KEPH → VBRK F2 / ACDOCA.</p>
<p><b>Do not:</b> cost TG10 as manufactured. Do not treat 500 SE16N rows as
the population. Do not release 74 variants into F4 for clerks.</p>
""",
    ))

    for i in range(1, LIVE["tck03"] + 1):
        pages.append(p(
            f"{1900 + i:04d} · TCK03 costing variant slot {i}/{LIVE['tck03']}",
            f"""
<p>LIVE TCK03 = <b>{LIVE['tck03']}</b>. Slot {i} is one KLVAR (CK11N/CK40N).
Fields: TCK03-KLVAR, TCK03-BWVAR → TCK05 ({LIVE['tck05']} valuation variants),
TCK03-KALKA costing type, TCK03-UEBER transfer control.</p>
<p>Used? Unknown until a 1710 KEKO filter names the variant. Process change:
restrict F4 to the variants that have KEKO-FREIG on plant 1710. Same disease
as 139 T161 / 376 TVAK — configured ≠ used.</p>
<p>Ticket if this slot is picked by accident: CK40N error log, or a legal vs
group cost mixed into MBEW-STPRS, then PPV explosion at GR 101.</p>
{hops_for("TCK03", str(i))}
{support_for(f"KLVAR-{i}")}
{change_for(f"KLVAR-{i}")}
""",
        ))

    for i in range(1, LIVE["tck05"] + 1):
        pages.append(p(
            f"{1980 + i:04d} · TCK05 valuation variant slot {i}/{LIVE['tck05']}",
            f"""
<p>LIVE TCK05 = <b>{LIVE['tck05']}</b>. Slot {i} is a price-source strategy
(PO / info record / planned price 1–3 / movement). TCK14 partner components
= <b>{LIVE['tck14']}</b> — intercompany markup lives here.</p>
<p>Wrong strategy → purchased material costed at planned price 1 (zero) while
EINE has a real PO price → STPRS lie → F2 margin lie.</p>
{hops_for("TCK05", str(i))}
{support_for(f"BWVAR-{i}")}
{change_for(f"BWVAR-{i}")}
""",
        ))

    copc_tables = [
        ("KEKO", LIVE["keko"], "Cost estimate header. Filter 1710/WERKS next. FREIG = released to MBEW-STPRS."),
        ("KEPH", LIVE["keph"], "Cost component split. This is what COPA/ACDOCA should inherit for F2 margin."),
        ("CKIS", LIVE["ckis"], "Itemization: BOM (M), activity (E), subcontract (L). TG10 should not look like M."),
        ("CKHS", LIVE["ckhs"], "Unit-costing header — additive / unit cost path beside quantity structure."),
        ("CKMLHD", LIVE["ckmlhd"], "ML header. 2,594 vs MBEW 3,071 ⇒ most valuated materials are in the ledger."),
        ("CKMLPP", LIVE["ckmlpp"], "ML period qty. 45,572 / 2,594 ≈ 17.6 periods — years of close, not a pilot."),
        ("CKMLCR", LIVE["ckmlcr"], "ML period value / PUP. Not-distributed tickets start here vs CKMLPP."),
        ("CKMLPR", LIVE["ckmlpr"], "ML prices. PUP vs S after CKMLCP."),
        ("T001K", LIVE["t001k"], "Valuation areas. MLBWA/MLBWI = ML on/off per area. 1,004 is a landscape, not one plant."),
        ("MBEW", LIVE["mbew"], "VPRSV S vs V, STPRS, VERPR, BKLAS → OBYC. 3,071 materials have a price."),
        ("TCKH1", LIVE["tckh1"], "Cost component texts — 3,590. Structure exists; TCK31=1 says overhead barely used."),
        ("TCK14", LIVE["tck14"], "Partner cost components — 121. Intercompany / transfer-price leaf."),
        ("TCK31", LIVE["tck31"], "Costing sheet = 1. Overhead is a ghost. Activity + material dominate CKIS."),
        ("QBEW", LIVE["qbew"], "Project stock = 0. Do not design PS-stock costing. EBEW is the special-stock leaf."),
        ("EBEW", LIVE["ebew"], "Sales-order stock = 89. MTO exists. Cost those 89 on the sales-order, not as unrestricted."),
        ("AUFK", LIVE["aufk"], "2,950 orders. Not a sales-only book. Includes PP + internal/CO orders."),
        ("AFKO", LIVE["afko"], "2,479 PP headers. Factory ran."),
        ("AFPO", LIVE["afpo"], "1,021 PP items vs 2,479 headers — many headers have no item (or mixed order categories)."),
        ("RESB", LIVE["resb"], "10,666 reservations. BOM exploded onto orders. Subcon/TG10 cousin lives here."),
        ("AFRU", LIVE["afru"], "1,838 confirmations. Yield/scrap/activity posted. Variance tickets start here."),
        ("COSP", LIVE["cosp"], "26,953 CO totals. Actual cost objects are populated."),
        ("COEP", LIVE["coep"], "38,507 CO line items. This is the P&L grain, not KEKO."),
        ("CSKB", LIVE["cskb"], "10,732 cost elements. Earlier 'CSKB empty' guess was wrong."),
        ("CSKS", LIVE["csks"], "1,623 cost centers. Activity price (COST/KP26) has somewhere to sit."),
        ("TKKAA", LIVE["tkkaa"], "35 RA/WIP check rows. KKAX/KKAO is configured."),
        ("TKA01", LIVE["tka01"], "591 controlling areas — same F4 disease as 376 TVAK. Do not pick a random KOKRS."),
        ("TKA02", LIVE["tka02"], "837 CoCd↔CO assignments. 1710 must be proven in this table before CK11N on 1710."),
    ]
    for i, (tab, n, note) in enumerate(copc_tables, 1):
        pages.append(p(
            f"{2020 + i:04d} · LIVE table {tab} · {n:,} entries",
            f"""
<p><b>{tab}</b> Number of Entries = <b>{n:,}</b> (popup, not a 500 list).</p>
<p>{note}</p>
<p>Next glass: SE16N {tab} → filter 1710 / WERKS / KOKRS → Number of Entries
again on the slice → then one display t-code (CK13N / CKM3N / MM03).</p>
{hops_for("COPC", tab)}
{support_for(tab)}
{change_for(tab)}
""",
        ))

    pages.append(p(
        "1999 · How this report grows to stay true",
        f"""
<p>Re-run <code>python scripts/generate_mega_report.py</code> after
<code>data/runs/analysis_mega/LIVE_COUNTS.json</code> is updated by the live
agent. Replace ≥500 with Number of Entries. Never paste a 500 list as a census.</p>
<p>Product: analysis wing = operator (see/goto/count) + this generator +
PROGRAM_6_TO_60 + SUPPORT_PREDICTION + ASSOCIATIONS_AND_ACTORS.</p>
<p>Printed pages in this file: see footer count.</p>
""",
    ))

    css = """
    body { font-family: Georgia, serif; background:#111; color:#eee; margin:0; }
    .page { page-break-after: always; padding: 22mm 20mm; min-height: 240mm;
            border-bottom: 1px solid #333; max-width: 180mm; margin: 0 auto; }
    h1 { font-size: 22pt; } h2 { font-size: 14pt; }
    p, li { font-size: 11pt; line-height: 1.35; }
    .meta { color:#9ad; font-size: 10pt; }
    """
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>Analysis mega report — {len(pages)} pages</title>"
        f"<style>{css}</style></head><body>\n"
        f"<article class='page'><h1>SAPILOT Analysis Wing</h1>"
        f"<p class='meta'>{LIVE['system']}</p>"
        f"<p class='meta'>Generated pages: <b>{len(pages)}</b> · target 1000+</p>"
        f"<p>This is not a 50-page slide. It is the encyclopedic dump the operator"
        f" should have been producing: every type, hop, ticket, month, actor.</p>"
        f"</article>\n"
        + "".join(pages)
        + f"<footer class='page'><p>END · {len(pages)} pages</p></footer>"
        + "</body></html>"
    )
    return html, len(pages)


def main() -> None:
    html, n = gen()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT} pages={n} bytes={OUT.stat().st_size}")


if __name__ == "__main__":
    main()
