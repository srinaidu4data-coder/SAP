from __future__ import annotations

from sapilot.copilot.engine import Copilot
from sapilot.copilot.scenarios import list_scenarios, load_scenario


def test_list_scenarios():
    scenarios = list_scenarios()
    ids = {s["id"] for s in scenarios}
    assert "f110_diagnose" in ids
    assert "f110_parameters" in ids
    assert "read_table" in ids
    assert "vendor_display" in ids


def test_copilot_f110_diagnose_mock():
    cp = Copilot(mock=True, cccategory="D")
    try:
        result = cp.run_scenario(
            "f110_diagnose",
            {
                "bukrs": "1000",
                "method": "A",
                "lifnr": "0000100001",
                "laufd": "20260812",
                "laufi": "ACH1",
            },
        )
        assert result["ok"] is True
        assert result["steps_run"] >= 3
        assert "fbzp" in result["vars"]
        assert "vendor" in result["vars"]
        assert cp.tier_ctx is not None
        assert cp.tier_ctx.tier.value == "T1_SANDBOX"
    finally:
        cp.disconnect()


def test_copilot_f110_parameters_clicks_mock():
    cp = Copilot(mock=True)
    try:
        result = cp.run_scenario(
            "f110_parameters",
            {
                "bukrs": "1000",
                "method": "A",
                "laufd": "20260812",
                "laufi": "DEMO01",
            },
        )
        assert result["ok"] is True
        # Driver history should include setText for run date
        assert cp.driver is not None
        actions = [h.get("action") for h in cp.driver.history]
        assert "tcode" in actions
        assert "setText" in actions
    finally:
        cp.disconnect()


def test_copilot_extract_table_mock():
    cp = Copilot(mock=True)
    try:
        data = cp.extract_table("T042", rowcount=10)
        assert data["channel"] == "rfc"
        assert data["count"] >= 1
    finally:
        cp.disconnect()


def test_load_scenario_yaml():
    sc = load_scenario("vendor_line_items")
    assert sc["id"] == "vendor_line_items"
    assert any(s.get("action") == "tcode" for s in sc["steps"])
