from __future__ import annotations

from sapilot.diagnose.engine import PaymentRunDiagnosticEngine
from sapilot.know.tables import KnowledgeTables


def test_diagnose_finds_blockers(mock_rfc):
    engine = PaymentRunDiagnosticEngine(KnowledgeTables(mock_rfc))
    report = engine.diagnose(
        company_code="1000",
        payment_method="A",
        vendors=["0000100001"],
        land1="US",
    )
    assert report.findings
    tables_hit = {f.cause_table for f in report.findings}
    # Expected from mock seed
    assert "T042E" in tables_hit or "T042I" in tables_hit
    assert any("ZWELS" in (f.cause_field or "") or "payment method" in f.symptom.lower() for f in report.findings)
    assert any(f.cause_table == "LFBK" for f in report.findings)
    assert any(f.cause_field == "ZAHLS" or f.cause_field == "ZLSPR" for f in report.findings)
    assert "1000" in report.summary or "blocker" in report.summary.lower()
