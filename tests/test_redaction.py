from __future__ import annotations

from sapilot.security.redaction import RedactionGate


def test_iban_and_stable_tokens():
    g = RedactionGate(salt="test")
    text = "Pay to IBAN DE89370400440532013000 account 123456789012"
    r1 = g.redact_text(text)
    r2 = g.redact_text(text)
    assert "DE89370400440532013000" not in r1
    assert "«" in r1
    assert r1 == r2  # stable


def test_field_id_redaction():
    g = RedactionGate()
    row = {"LIFNR": "0000100001", "BANKN": "1234567890", "BANKL": "021000021"}
    out = g.redact_dict(row)
    assert out["BANKN"] != "1234567890"
    assert out["BANKN"].startswith("«")
    assert out["LIFNR"] == "0000100001"
