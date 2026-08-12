"""Order-to-Cash (OTC) demo tables for autonomous bot."""

from __future__ import annotations

from sapilot.connect.rfc import MockRfcClient
from sapilot.demo_data_ptp import seed_ptp_tables


def seed_otc_tables(rfc: MockRfcClient) -> None:
    """Customer → SO → Delivery → PGI → Billing → open AR → payment readiness."""
    seed_ptp_tables(rfc)  # materials shared

    # Customer master
    rfc.seed(
        "KNA1",
        [
            {
                "KUNNR": "0000001000",
                "NAME1": "Demo Customer Inc",
                "LAND1": "US",
                "SPERR": "",
                "LOEVM": "",
            }
        ],
    )
    rfc.seed(
        "KNB1",
        [
            {
                "KUNNR": "0000001000",
                "BUKRS": "1000",
                "AKONT": "140000",
                "ZTERM": "NT30",
                "ZWELS": "C",
                "SPERR": "",
            }
        ],
    )
    rfc.seed(
        "KNVV",
        [
            {
                "KUNNR": "0000001000",
                "VKORG": "1000",
                "VTWEG": "10",
                "SPART": "00",
                "WAERS": "USD",
                "ZTERM": "NT30",
                "VKBUR": "1000",
                "VKGRP": "001",
            }
        ],
    )

    # Sales org
    rfc.seed("TVKO", [{"VKORG": "1000", "VTEXT": "Sales Org 1000", "BUKRS": "1000"}])
    rfc.seed("TVTW", [{"VTWEG": "10", "VTEXT": "Direct"}])
    rfc.seed("TSPA", [{"SPART": "00", "VTEXT": "Product"}])

    # Material sales view (MVKE)
    rfc.seed(
        "MVKE",
        [
            {
                "MATNR": "000000000000100000",
                "VKORG": "1000",
                "VTWEG": "10",
                "VRKME": "EA",
                "DWERK": "1000",
            }
        ],
    )

    # Customer-material info
    rfc.seed(
        "KNMT",
        [
            {
                "VKORG": "1000",
                "VTWEG": "10",
                "KUNNR": "0000001000",
                "MATNR": "000000000000100000",
                "KDMAT": "CUST-MAT-100",
            }
        ],
    )

    # Sales order
    rfc.seed(
        "VBAK",
        [
            {
                "VBELN": "0000001001",
                "AUART": "OR",
                "VKORG": "1000",
                "VTWEG": "10",
                "SPART": "00",
                "KUNNR": "0000001000",
                "NETWR": "2500.00",
                "WAERK": "USD",
                "AUDAT": "20260810",
                "VBTYP": "C",
            }
        ],
    )
    rfc.seed(
        "VBAP",
        [
            {
                "VBELN": "0000001001",
                "POSNR": "000010",
                "MATNR": "000000000000100000",
                "WERKS": "1000",
                "KWMENG": "50",
                "VRKME": "EA",
                "NETWR": "2500.00",
                "WAERK": "USD",
            }
        ],
    )

    # Delivery
    rfc.seed(
        "LIKP",
        [
            {
                "VBELN": "0080001001",
                "LFART": "LF",
                "KUNNR": "0000001000",
                "VKORG": "1000",
                "WADAT": "20260811",
                "WADAT_IST": "20260811",
                "VBTYP": "J",
            }
        ],
    )
    rfc.seed(
        "LIPS",
        [
            {
                "VBELN": "0080001001",
                "POSNR": "000010",
                "MATNR": "000000000000100000",
                "WERKS": "1000",
                "LFIMG": "50",
                "VRKME": "EA",
                "VGBEL": "0000001001",
                "VGPOS": "000010",
            }
        ],
    )

    # Billing
    rfc.seed(
        "VBRK",
        [
            {
                "VBELN": "0090001001",
                "FKART": "F2",
                "VKORG": "1000",
                "VTWEG": "10",
                "KUNAG": "0000001000",
                "NETWR": "2500.00",
                "WAERK": "USD",
                "FKDAT": "20260812",
                "BUKRS": "1000",
            }
        ],
    )
    rfc.seed(
        "VBRP",
        [
            {
                "VBELN": "0090001001",
                "POSNR": "000010",
                "MATNR": "000000000000100000",
                "FKIMG": "50",
                "NETWR": "2500.00",
                "VGBEL": "0080001001",
                "VGPOS": "000010",
            }
        ],
    )

    # Customer open items (AR)
    rfc.seed(
        "BSID",
        [
            {
                "BUKRS": "1000",
                "KUNNR": "0000001000",
                "BELNR": "1800000001",
                "GJAHR": "2026",
                "BUZEI": "001",
                "WRBTR": "2500.00",
                "WAERS": "USD",
                "ZFBDT": "20260911",
                "ZTERM": "NT30",
                "ZLSPR": "",
                "XBLNR": "INV-SO-1001",
                "VBELN": "0090001001",
            }
        ],
    )

    # Document flow stub
    rfc.seed(
        "VBFA",
        [
            {
                "VBELV": "0000001001",
                "POSNV": "000010",
                "VBELN": "0080001001",
                "POSNN": "000010",
                "VBTYP_N": "J",
            },
            {
                "VBELV": "0080001001",
                "POSNV": "000010",
                "VBELN": "0090001001",
                "POSNN": "000010",
                "VBTYP_N": "M",
            },
        ],
    )
