"""Built-in demo SAP tables for offline diagnose + agent demos."""

from __future__ import annotations

from sapilot.connect.rfc import MockRfcClient


def seed_demo_tables(rfc: MockRfcClient) -> None:
    """Intentionally broken ACH setup for company 1000."""
    rfc.seed(
        "T000",
        [
            {
                "MANDT": "100",
                "MTEXT": "Sandbox",
                "ORT01": "Demo",
                "CCCATEGORY": "D",
                "CCCORACTIV": "1",
            }
        ],
    )
    rfc.seed("T042", [{"BUKRS": "1000", "ZBUKR": "1000", "TOLTG": "0"}])
    rfc.seed("T042B", [{"ZBUKR": "1000", "MINBL": "0"}])
    rfc.seed(
        "T042Z",
        [{"LAND1": "US", "ZLSCH": "A", "TEXT1": "ACH", "XPGIR": "X"}],
    )
    rfc.seed("T042E", [])
    rfc.seed("T042I", [])
    rfc.seed("T042A", [])
    rfc.seed(
        "T042Y",
        [{"ZBUKR": "1000", "HBKID": "HOME", "HKTID": "OPER", "MAXBT": "0"}],
    )
    rfc.seed("T012", [{"BUKRS": "1000", "HBKID": "HOME", "BANKS": "US", "BANKL": "021000021"}])
    rfc.seed(
        "T012K",
        [
            {
                "BUKRS": "1000",
                "HBKID": "HOME",
                "HKTID": "OPER",
                "BANKN": "999999999",
                "HKONT": "113100",
            }
        ],
    )
    rfc.seed(
        "LFA1",
        [
            {
                "LIFNR": "0000100001",
                "NAME1": "Demo Vendor LLC",
                "LAND1": "US",
                "SPERR": "",
                "SPERM": "",
                "LOEVM": "",
            }
        ],
    )
    rfc.seed(
        "LFB1",
        [
            {
                "LIFNR": "0000100001",
                "BUKRS": "1000",
                "ZWELS": "C",
                "ZTERM": "NT30",
                "ZAHLS": "A",
                "HBKID": "",
                "ZINDT": "",
                "SPERR": "",
            }
        ],
    )
    rfc.seed("LFBK", [])
    rfc.seed("BNKA", [{"BANKS": "US", "BANKL": "021000021", "BANKA": "JPMORGAN", "ORT01": "NY"}])
    rfc.seed(
        "BSIK",
        [
            {
                "BUKRS": "1000",
                "LIFNR": "0000100001",
                "BELNR": "1900000001",
                "GJAHR": "2026",
                "BUZEI": "001",
                "WRBTR": "1500.00",
                "WAERS": "USD",
                "ZFBDT": "20260801",
                "ZTERM": "NT30",
                "ZLSPR": "A",
                "ZLSCH": "",
                "SHKZG": "H",
            }
        ],
    )
    rfc.seed("REGUV", [])
    rfc.seed("REGUP", [])
    rfc.seed("REGUH", [])
    rfc.seed(
        "T100",
        [
            {
                "SPRSL": "E",
                "ARBGB": "FZ",
                "MSGNR": "001",
                "TEXT": "No valid payment method found for &",
            }
        ],
    )
