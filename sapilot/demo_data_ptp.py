"""Realistic PTP (Procure-to-Pay) demo tables for offline Co-pilot runs."""

from __future__ import annotations

from sapilot.connect.rfc import MockRfcClient
from sapilot.demo_data import seed_demo_tables


def seed_ptp_tables(rfc: MockRfcClient) -> None:
    """Extend mock store with end-to-end P2P master + transactional data."""
    seed_demo_tables(rfc)  # keeps F110/AP demo vendor

    # Purchasing org / plant
    rfc.seed("T024E", [{"EKORG": "1000", "EKOTX": "Main Purch. Org", "BUKRS": "1000"}])
    rfc.seed("T001W", [{"WERKS": "1000", "NAME1": "Plant 1000", "BWKEY": "1000", "EKORG": "1000"}])
    rfc.seed("T024", [{"EKGRP": "001", "EKNAM": "Buyers"}])

    # Material for PO
    rfc.seed(
        "MARA",
        [
            {
                "MATNR": "000000000000100000",
                "MTART": "ROH",
                "MEINS": "EA",
                "MATKL": "001",
                "ERSDA": "20260101",
            }
        ],
    )
    rfc.seed(
        "MARC",
        [
            {
                "MATNR": "000000000000100000",
                "WERKS": "1000",
                "EKGRP": "001",
                "BESKZ": "F",
                "MMSTA": "",
            }
        ],
    )
    rfc.seed(
        "MBEW",
        [
            {
                "MATNR": "000000000000100000",
                "BWKEY": "1000",
                "VPRSV": "S",
                "STPRS": "10.00",
                "PEINH": "1",
                "BKLAS": "3000",
            }
        ],
    )

    # Vendor purchasing data (same vendor as FI demo)
    rfc.seed(
        "LFM1",
        [
            {
                "LIFNR": "0000100001",
                "EKORG": "1000",
                "WAERS": "USD",
                "ZTERM": "NT30",
                "INCO1": "FOB",
                "SPERM": "",
                "LOEVM": "",
            }
        ],
    )

    # Purchasing info record
    rfc.seed(
        "EINA",
        [
            {
                "INFNR": "5300000001",
                "MATNR": "000000000000100000",
                "LIFNR": "0000100001",
                "ERDAT": "20260115",
            }
        ],
    )
    rfc.seed(
        "EINE",
        [
            {
                "INFNR": "5300000001",
                "EKORG": "1000",
                "ESOKZ": "0",
                "WERKS": "1000",
                "NETPR": "12.50",
                "PEINH": "1",
                "BPRME": "EA",
                "MWSKZ": "I0",
            }
        ],
    )

    # Source list
    rfc.seed(
        "EORD",
        [
            {
                "MATNR": "000000000000100000",
                "WERKS": "1000",
                "ZEORD": "0001",
                "VDATU": "20260101",
                "BDATU": "99991231",
                "LIFNR": "0000100001",
                "EKORG": "1000",
                "FLIFN": "X",
            }
        ],
    )

    # Purchase requisition
    rfc.seed(
        "EBAN",
        [
            {
                "BANFN": "0010000001",
                "BNFPO": "00010",
                "BSART": "NB",
                "STATU": "N",
                "MATNR": "000000000000100000",
                "WERKS": "1000",
                "LGORT": "0001",
                "MENGE": "100",
                "MEINS": "EA",
                "LFDAT": "20260820",
                "EKGRP": "001",
                "EKORG": "1000",
                "FLIEF": "0000100001",
                "BADAT": "20260810",
                "LOEKZ": "",
            }
        ],
    )

    # Purchase order header/items
    rfc.seed(
        "EKKO",
        [
            {
                "EBELN": "4500000001",
                "BUKRS": "1000",
                "BSTYP": "F",
                "BSART": "NB",
                "STATU": "9",
                "LIFNR": "0000100001",
                "EKORG": "1000",
                "EKGRP": "001",
                "WAERS": "USD",
                "BEDAT": "20260811",
                "FRGKE": "",
                "FRGZU": "",
                "LOEKZ": "",
            }
        ],
    )
    rfc.seed(
        "EKPO",
        [
            {
                "EBELN": "4500000001",
                "EBELP": "00010",
                "MATNR": "000000000000100000",
                "WERKS": "1000",
                "LGORT": "0001",
                "MENGE": "100",
                "MEINS": "EA",
                "NETPR": "12.50",
                "PEINH": "1",
                "NETWR": "1250.00",
                "MWSKZ": "I0",
                "KNTTP": "",
                "LOEKZ": "",
                "ELIKZ": "",
                "EREKZ": "",
            }
        ],
    )

    # PO history (GR + IR)
    rfc.seed(
        "EKBE",
        [
            {
                "EBELN": "4500000001",
                "EBELP": "00010",
                "ZEKKN": "00",
                "VGABE": "1",
                "GJAHR": "2026",
                "BELNR": "5000000001",
                "BUZEI": "1",
                "BEWTP": "E",
                "BWART": "101",
                "MENGE": "100",
                "WRBTR": "1250.00",
                "SHKZG": "S",
                "BUDAT": "20260812",
            },
            {
                "EBELN": "4500000001",
                "EBELP": "00010",
                "ZEKKN": "00",
                "VGABE": "2",
                "GJAHR": "2026",
                "BELNR": "5105600001",
                "BUZEI": "1",
                "BEWTP": "Q",
                "BWART": "",
                "MENGE": "100",
                "WRBTR": "1250.00",
                "SHKZG": "H",
                "BUDAT": "20260813",
            },
        ],
    )

    # Material document GR
    rfc.seed(
        "MKPF",
        [{"MBLNR": "5000000001", "MJAHR": "2026", "BLDAT": "20260812", "BUDAT": "20260812", "VGART": "WE"}],
    )
    rfc.seed(
        "MSEG",
        [
            {
                "MBLNR": "5000000001",
                "MJAHR": "2026",
                "ZEILE": "0001",
                "BWART": "101",
                "MATNR": "000000000000100000",
                "WERKS": "1000",
                "LGORT": "0001",
                "LIFNR": "0000100001",
                "EBELN": "4500000001",
                "EBELP": "00010",
                "MENGE": "100",
                "MEINS": "EA",
                "SHKZG": "S",
            }
        ],
    )

    # Invoice document
    rfc.seed(
        "RBKP",
        [
            {
                "BELNR": "5105600001",
                "GJAHR": "2026",
                "BLART": "RE",
                "BLDAT": "20260813",
                "BUDAT": "20260813",
                "XBLNR": "INV-9001",
                "LIFNR": "0000100001",
                "WAERS": "USD",
                "RMWWR": "1250.00",
                "RBSTAT": "5",
                "BUKRS": "1000",
            }
        ],
    )
    rfc.seed(
        "RSEG",
        [
            {
                "BELNR": "5105600001",
                "GJAHR": "2026",
                "BUZEI": "0001",
                "EBELN": "4500000001",
                "EBELP": "00010",
                "MATNR": "000000000000100000",
                "WRBTR": "1250.00",
                "MENGE": "100",
                "BSTME": "EA",
                "BUKRS": "1000",
            }
        ],
    )

    # Open vendor items after invoice (for payment)
    # demo_data already has blocked BSIK; add clean open item for PO invoice
    existing = list(rfc.tables.get("BSIK", []))
    existing.append(
        {
            "BUKRS": "1000",
            "LIFNR": "0000100001",
            "BELNR": "1900000099",
            "GJAHR": "2026",
            "BUZEI": "001",
            "WRBTR": "1250.00",
            "WAERS": "USD",
            "ZFBDT": "20260912",
            "ZTERM": "NT30",
            "ZLSPR": "",
            "ZLSCH": "A",
            "SHKZG": "H",
            "XBLNR": "INV-9001",
            "EBELN": "4500000001",
        }
    )
    rfc.seed("BSIK", existing)

    # Account assignment category / tax codes reference
    rfc.seed("T163K", [{"KNTTP": "K", "KNTXT": "Cost center"}])
    rfc.seed("T007A", [{"KALSM": "TAXUS", "MWSKZ": "I0", "MWART": "V", "TEXT1": "Input tax 0%"}])
