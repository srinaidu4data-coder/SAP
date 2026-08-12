"""
SAP GUI navigation catalog — consultant playbook encoded from industry practice.

Research sources (not 10k videos, but the same patterns those tutorials teach):
  - SAP Community: findById okcd + sendVKey 0 for navigation
  - Script Recording & Playback → field IDs
  - S/4HANA: XK03/FK03 redirect to BP (Display Supplier) — Supplier ≠ tcode
  - BAPI/COM hybrid: StartTransaction preferred over guessing screen clicks

Golden rules:
  1. NEVER type /nTCODE into dynpro data fields (Supplier, Material, PO…)
  2. Navigate ONLY via session.StartTransaction OR toolbar okcd
  3. Then fill business keys with correct field IDs for that tcode
  4. Enter = sendVKey(0); F8 = sendVKey(8); Back = sendVKey(3)
"""

from __future__ import annotations

from typing import Any

# sendVKey map (standard SAP GUI Scripting)
VKEY = {
    "Enter": 0,
    "F2": 2,
    "F3": 3,  # Back
    "F4": 4,  # Matchcode
    "F5": 5,
    "F8": 8,  # Execute
    "F12": 12,  # Cancel
}

# Primary navigation: always StartTransaction or okcd — never mouse-guess form body
NAVIGATE = {
    "method": "com_start_transaction",  # session.StartTransaction(tcode)
    "fallback_okcd": "wnd[0]/tbar[0]/okcd",
    "enter_vkey": 0,
}

# Per-tcode: fields to fill AFTER correct navigation (business data only)
# Each field: list of FindById candidates (first that works wins)
TCODE_SCREENS: dict[str, dict[str, Any]] = {
    "BP": {
        "title_contains": ["Business Partner", "Display Supplier", "Supplier"],
        "fields": {
            "PARTNER": [
                "wnd[0]/usr/ctxtBUS_JOEL_SEARCH-PARTNER_NUMBER",
                "wnd[0]/usr/ctxtPARTNER",
                "wnd[0]/usr/txtBUS_JOEL_SEARCH-PARTNER_NUMBER",
            ],
            "LIFNR": [
                "wnd[0]/usr/ctxtBUS_JOEL_SEARCH-PARTNER_NUMBER",
                "wnd[0]/usr/ctxtRF02K-LIFNR",
                "wnd[0]/usr/ctxtPARTNER",
            ],
        },
        "notes": "S/4 Display Supplier is BP — put BP/vendor number, never a tcode",
    },
    "XK03": {
        "title_contains": ["Display Vendor", "Display Supplier", "Vendor", "Supplier", "Business Partner"],
        "redirects_to": "BP",  # S/4 often lands on BP
        "fields": {
            "LIFNR": [
                "wnd[0]/usr/ctxtRF02K-LIFNR",
                "wnd[0]/usr/txtRF02K-LIFNR",
                "wnd[0]/usr/ctxtBUS_JOEL_SEARCH-PARTNER_NUMBER",
                "wnd[0]/usr/ctxtPARTNER",
            ],
            "BUKRS": [
                "wnd[0]/usr/ctxtRF02K-BUKRS",
                "wnd[0]/usr/txtRF02K-BUKRS",
            ],
            "EKORG": [
                "wnd[0]/usr/ctxtRF02K-EKORG",
                "wnd[0]/usr/txtRF02K-EKORG",
            ],
        },
        "checkboxes_optional": [
            "wnd[0]/usr/chkRF02K-D0110",  # address
            "wnd[0]/usr/chkRF02K-D0120",
        ],
        "after_fill_vkey": 0,
    },
    "FK03": {
        "alias_of": "XK03",
    },
    "MM03": {
        "fields": {
            "MATNR": [
                "wnd[0]/usr/ctxtRMMG1-MATNR",
                "wnd[0]/usr/txtRMMG1-MATNR",
            ],
        },
        "after_fill_vkey": 0,
    },
    "ME13": {
        "fields": {
            "LIFNR": [
                "wnd[0]/usr/ctxtEINE-LIFNR",
                "wnd[0]/usr/ctxtLIFNR",
            ],
            "MATNR": [
                "wnd[0]/usr/ctxtEINE-MATNR",
                "wnd[0]/usr/ctxtMATNR",
            ],
            "EKORG": [
                "wnd[0]/usr/ctxtEINE-EKORG",
                "wnd[0]/usr/ctxtEKORG",
            ],
        },
        "after_fill_vkey": 0,
    },
    "ME03": {
        "fields": {
            "MATNR": ["wnd[0]/usr/ctxtMATNR", "wnd[0]/usr/ctxtRM06W-MATNR"],
            "WERKS": ["wnd[0]/usr/ctxtWERKS", "wnd[0]/usr/ctxtRM06W-WERKS"],
        },
        "after_fill_vkey": 0,
    },
    "ME53N": {
        "fields": {
            "BANFN": [
                "wnd[0]/usr/subSUB0:SAPLMEGUI:0016/subSUB2:SAPLMEVIEWS:1100/"
                "subSUB1:SAPLMEGUI:1102/ctxtMEPO_SELECT-BANFN",
                "wnd[0]/usr/ctxtMEPO_SELECT-BANFN",
                "wnd[0]/usr/ctxtBANFN",
            ],
        },
        "after_fill_vkey": 0,
    },
    "ME23N": {
        "fields": {
            "EBELN": [
                "wnd[0]/usr/subSUB0:SAPLMEGUI:0013/subSUB2:SAPLMEVIEWS:1100/"
                "subSUB1:SAPLMEGUI:1102/ctxtMEPO_SELECT-EBELN",
                "wnd[0]/usr/ctxtMEPO_SELECT-EBELN",
                "wnd[0]/usr/ctxtEBELN",
            ],
        },
        "after_fill_vkey": 0,
    },
    "ME21N": {
        "fields": {
            "LIFNR": [
                "wnd[0]/usr/subSUB0:SAPLMEGUI:0013/subSUB1:SAPLMEVIEWS:1100/"
                "subSUB1:SAPLMEGUI:1102/ctxtMEPO_TOPLINE-SUPERFIELD",
                "wnd[0]/usr/ctxtMEPO_TOPLINE-SUPERFIELD",
            ],
        },
        "notes": "Create PO — prefer BAPI_PO_CREATE1 for bulk create",
    },
    "MIGO": {
        "fields": {
            "EBELN": [
                "wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0003/"
                "subSUB_FIRSTLINE:SAPLMIGO:0010/subSUB_FIRSTLINE_REFDOC:SAPLMIGO:2000/ctxtGODYNPRO-PO_NUMBER",
                "wnd[0]/usr/ctxtGODYNPRO-PO_NUMBER",
                "wnd[0]/usr/ctxtEBELN",
            ],
        },
        "after_fill_vkey": 0,
    },
    "MIR4": {
        "fields": {
            "BELNR": [
                "wnd[0]/usr/txtRBKPV-BELNR",
                "wnd[0]/usr/ctxtRBKPV-BELNR",
                "wnd[0]/usr/txtBELNR",
            ],
            "GJAHR": [
                "wnd[0]/usr/txtRBKPV-GJAHR",
                "wnd[0]/usr/txtGJAHR",
            ],
        },
        "after_fill_vkey": 0,
    },
    "FBL1N": {
        "fields": {
            "LIFNR": [
                "wnd[0]/usr/ctxtKD_LIFNR-LOW",
                "wnd[0]/usr/ctxtLIFNR-LOW",
            ],
            "BUKRS": [
                "wnd[0]/usr/ctxtKD_BUKRS-LOW",
                "wnd[0]/usr/ctxtBUKRS-LOW",
            ],
        },
        "after_fill_vkey": 8,  # F8 execute
    },
    "F110": {
        "fields": {
            "LAUFD": [
                "wnd[0]/usr/txtF110V-LAUFD",
                "wnd[0]/usr/ctxtF110V-LAUFD",
            ],
            "LAUFI": [
                "wnd[0]/usr/txtF110V-LAUFI",
                "wnd[0]/usr/ctxtF110V-LAUFI",
            ],
        },
        "after_fill_vkey": 0,
        "notes": "Payment program — parameters only unless T1",
    },
    "SE16N": {
        "fields": {
            "TABNAME": [
                "wnd[0]/usr/ctxtGD-TAB",
                "wnd[0]/usr/ctxtGS_SE16N-TAB",
            ],
        },
        "after_fill_vkey": 8,
    },
    "SE16": {
        "fields": {
            "TABNAME": [
                "wnd[0]/usr/ctxtDATABROWSE-TABLENAME",
            ],
        },
        "after_fill_vkey": 0,
    },
    # ---- Order-to-Cash ----
    "XD03": {
        "title_contains": ["Display Customer", "Customer", "Business Partner"],
        "redirects_to": "BP",
        "fields": {
            "KUNNR": [
                "wnd[0]/usr/ctxtRF02D-KUNNR",
                "wnd[0]/usr/txtRF02D-KUNNR",
                "wnd[0]/usr/ctxtBUS_JOEL_SEARCH-PARTNER_NUMBER",
            ],
            "BUKRS": ["wnd[0]/usr/ctxtRF02D-BUKRS", "wnd[0]/usr/txtRF02D-BUKRS"],
            "VKORG": ["wnd[0]/usr/ctxtRF02D-VKORG"],
        },
        "after_fill_vkey": 0,
    },
    "VA03": {
        "fields": {
            "VBELN": [
                "wnd[0]/usr/ctxtVBAK-VBELN",
                "wnd[0]/usr/txtVBAK-VBELN",
                "wnd[0]/usr/ctxtVBELN",
            ],
        },
        "after_fill_vkey": 0,
    },
    "VL03N": {
        "fields": {
            "VBELN": [
                "wnd[0]/usr/ctxtLIKP-VBELN",
                "wnd[0]/usr/txtLIKP-VBELN",
                "wnd[0]/usr/ctxtVBELN",
            ],
        },
        "after_fill_vkey": 0,
    },
    "VF03": {
        "fields": {
            "VBELN": [
                "wnd[0]/usr/ctxtVBRK-VBELN",
                "wnd[0]/usr/txtVBRK-VBELN",
                "wnd[0]/usr/ctxtVBELN",
            ],
        },
        "after_fill_vkey": 0,
    },
    "FBL5N": {
        "fields": {
            "KUNNR": [
                "wnd[0]/usr/ctxtDD_KUNNR-LOW",
                "wnd[0]/usr/ctxtKUNNR-LOW",
                "wnd[0]/usr/ctxtKD_KUNNR-LOW",
            ],
            "BUKRS": [
                "wnd[0]/usr/ctxtDD_BUKRS-LOW",
                "wnd[0]/usr/ctxtBUKRS-LOW",
                "wnd[0]/usr/ctxtKD_BUKRS-LOW",
            ],
        },
        "after_fill_vkey": 8,
    },
    "F-28": {
        "fields": {
            "KUNNR": ["wnd[0]/usr/ctxtRF05A-KUNNR", "wnd[0]/usr/ctxtKUNNR"],
            "BUKRS": ["wnd[0]/usr/ctxtRF05A-BUKRS", "wnd[0]/usr/ctxtBUKRS"],
        },
        "after_fill_vkey": 0,
        "notes": "Incoming payment — display/params only unless T1",
    },
    # ---- ABAP debug (read-only — never debugger field replace) ----
    "ST22": {
        "title_contains": ["ABAP Runtime Errors", "Runtime Error", "Dump"],
        "fields": {
            "UNAME": [
                "wnd[0]/usr/ctxtS_UNAME-LOW",
                "wnd[0]/usr/ctxtUNAME-LOW",
            ],
            "DATUM": [
                "wnd[0]/usr/ctxtS_DATUM-LOW",
                "wnd[0]/usr/ctxtDATUM-LOW",
            ],
        },
        "after_fill_vkey": 8,
        "notes": "ST22 dump list — display only",
    },
    "SE38": {
        "title_contains": ["ABAP Editor", "Program"],
        "fields": {
            "PROGRAM": [
                "wnd[0]/usr/ctxtRS38M-PROGRAMM",
                "wnd[0]/usr/ctxtPROGRAM",
                "wnd[0]/usr/txtRS38M-PROGRAMM",
            ],
        },
        "after_fill_vkey": 0,
        "notes": "SE38 display source — never change values in debugger",
    },
}

# Mission id → tcode + which keys to fill from twin/params
MISSION_NAV: dict[str, dict[str, Any]] = {
    "S1_VENDOR": {
        "tcode": "XK03",
        "fill": {"LIFNR": "lifnr", "BUKRS": "bukrs"},
        "defaults": {"lifnr": "0000100001", "bukrs": "1000"},
    },
    "S2_MATERIAL": {
        "tcode": "MM03",
        "fill": {"MATNR": "matnr"},
        "defaults": {"matnr": "000000000000100000"},
    },
    "S3_INFO": {
        "tcode": "ME13",
        "fill": {"LIFNR": "lifnr", "MATNR": "matnr", "EKORG": "ekorg"},
        "defaults": {
            "lifnr": "0000100001",
            "matnr": "000000000000100000",
            "ekorg": "1000",
        },
    },
    "S4_SOURCE": {
        "tcode": "ME03",
        "fill": {"MATNR": "matnr", "WERKS": "werks"},
        "defaults": {"matnr": "000000000000100000", "werks": "1000"},
    },
    "S5_PR": {
        "tcode": "ME53N",
        "fill": {"BANFN": "banfn"},
        "defaults": {"banfn": "0010000001"},
    },
    "S6_PO": {
        "tcode": "ME23N",
        "fill": {"EBELN": "ebeln"},
        "defaults": {"ebeln": "4500000001"},
    },
    "S7_GR": {
        "tcode": "MIGO",
        "fill": {"EBELN": "ebeln"},
        "defaults": {"ebeln": "4500000001"},
    },
    "S8_IR": {
        "tcode": "MIR4",
        "fill": {"BELNR": "belnr_inv", "GJAHR": "gjahr"},
        "defaults": {"belnr_inv": "5105600001", "gjahr": "2026"},
    },
    "S9_OPEN_ITEMS": {
        "tcode": "FBL1N",
        "fill": {"LIFNR": "lifnr", "BUKRS": "bukrs"},
        "defaults": {"lifnr": "0000100001", "bukrs": "1000"},
    },
    "S10_PAYMENT": {
        "tcode": "F110",
        "fill": {"LAUFD": "laufd", "LAUFI": "laufi"},
        "defaults": {"laufd": "20260812", "laufi": "PTP001"},
    },
    # OTC missions
    "O1_CUSTOMER": {
        "tcode": "XD03",
        "fill": {"KUNNR": "kunnr", "BUKRS": "bukrs"},
        "defaults": {"kunnr": "0000001000", "bukrs": "1000"},
    },
    "O2_MAT_SALES": {
        "tcode": "MM03",
        "fill": {"MATNR": "matnr"},
        "defaults": {"matnr": "000000000000100000"},
    },
    "O3_CUST_MAT": {
        "tcode": "VD53",
        "fill": {},
        "defaults": {},
    },
    "O4_SALES_ORG": {
        "tcode": "OVX5",
        "fill": {},
        "defaults": {},
    },
    "O5_SO": {
        "tcode": "VA03",
        "fill": {"VBELN": "vbeln_so"},
        "defaults": {"vbeln_so": "0000001001"},
    },
    "O6_DN": {
        "tcode": "VL03N",
        "fill": {"VBELN": "vbeln_dn"},
        "defaults": {"vbeln_dn": "0080001001"},
    },
    "O7_GI": {
        "tcode": "VL03N",
        "fill": {"VBELN": "vbeln_dn"},
        "defaults": {"vbeln_dn": "0080001001"},
    },
    "O8_BILL": {
        "tcode": "VF03",
        "fill": {"VBELN": "vbeln_bill"},
        "defaults": {"vbeln_bill": "0090001001"},
    },
    "O9_AR": {
        "tcode": "FBL5N",
        "fill": {"KUNNR": "kunnr", "BUKRS": "bukrs"},
        "defaults": {"kunnr": "0000001000", "bukrs": "1000"},
    },
    "O10_INCOMING": {
        "tcode": "F-28",
        "fill": {"KUNNR": "kunnr", "BUKRS": "bukrs"},
        "defaults": {"kunnr": "0000001000", "bukrs": "1000"},
    },
    "A1_ST22_DUMP": {
        "tcode": "ST22",
        "fill": {"UNAME": "uname", "DATUM": "datum"},
        "defaults": {"uname": "SV3_000349", "datum": "20260812"},
    },
    "A2_SE38_SOURCE": {
        "tcode": "SE38",
        "fill": {"PROGRAM": "program"},
        "defaults": {"program": "ZSAP_DEMO_INVOICE"},
    },
}


def resolve_screen(tcode: str) -> dict[str, Any]:
    t = tcode.upper().strip()
    scr = TCODE_SCREENS.get(t, {})
    if scr.get("alias_of"):
        return TCODE_SCREENS.get(scr["alias_of"], scr)
    return scr
