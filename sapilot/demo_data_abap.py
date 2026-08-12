"""ABAP debugging demo tables — ST22 dumps + program catalog (read-only inspect)."""

from __future__ import annotations

from sapilot.connect.rfc import MockRfcClient


def seed_abap_tables(rfc: MockRfcClient) -> None:
    """
    Seed tables used for ABAP debug scenarios (never field-value replace).
    Research: ST22 uses SNAP*; SE38 uses TRDIR / REPOSRC-style metadata.
    """
    # Runtime error snapshot (simplified SNAP / ST22 header)
    rfc.seed(
        "SNAP",
        [
            {
                "DATUM": "20260812",
                "UZEIT": "103045",
                "AHOST": "sapvista",
                "UNAME": "SV3_000349",
                "MANDT": "100",
                "MODNO": "001",
                "SEQNO": "00001",
                "FLIST": "MESSAGE",
                "FLENGTH": "80",
                "FVALUE": "COMPUTE_INT_ZERODIVIDE",
                "PROGRAM": "ZSAP_DEMO_INVOICE",
                "INCLUDE": "ZSAP_DEMO_INVOICE",
                "LINE": "000142",
            }
        ],
    )
    # Dump directory (common ST22 selection view fields)
    rfc.seed(
        "SNAP_BEG",
        [
            {
                "DATUM": "20260812",
                "UZEIT": "103045",
                "AHOST": "sapvista",
                "UNAME": "SV3_000349",
                "MANDT": "100",
                "SEQNO": "00001",
                "ERRID": "COMPUTE_INT_ZERODIVIDE",
                "PROGRAM": "ZSAP_DEMO_INVOICE",
                "TCODE": "MIRO",
            }
        ],
    )
    # Program catalog
    rfc.seed(
        "TRDIR",
        [
            {
                "NAME": "ZSAP_DEMO_INVOICE",
                "SUBC": "1",
                "CNAM": "DEMO",
                "CDAT": "20260115",
                "UNAM": "DEMO",
                "UDAT": "20260810",
                "RSTAT": "P",
                "DBAPL": "S",
            },
            {
                "NAME": "ZSAP_DEMO_PAYMENT",
                "SUBC": "1",
                "CNAM": "DEMO",
                "CDAT": "20260201",
                "UNAM": "DEMO",
                "UDAT": "20260811",
                "RSTAT": "P",
                "DBAPL": "S",
            },
        ],
    )
    # Function modules (SE37 style inspect)
    rfc.seed(
        "TFDIR",
        [
            {
                "FUNCNAME": "BAPI_PO_CREATE1",
                "PNAME": "SAPL2012",
                "INCLUDE": "L2012UXX",
                "FREEDATE": "",
            },
            {
                "FUNCNAME": "BAPI_INCOMINGINVOICE_CREATE",
                "PNAME": "SAPLMRM_BAPI",
                "INCLUDE": "LMRM_BAPIUXX",
                "FREEDATE": "",
            },
        ],
    )
    # Debug recipe store (bot training — no field replace)
    rfc.seed(
        "ZBOT_DEBUG_RECIPE",
        [
            {
                "RECIPE_ID": "DBG_ZERODIVIDE_01",
                "ERRID": "COMPUTE_INT_ZERODIVIDE",
                "PROGRAM": "ZSAP_DEMO_INVOICE",
                "LINE": "000142",
                "ROOT_CAUSE": "Quantity divisor zero before NETWR calc",
                "FIX_HINT": "Guard MENGE/PEINH before division; check invoice item qty",
                "TCODE": "SE38",
                "SAFE": "X",  # read-only inspect only
            }
        ],
    )
