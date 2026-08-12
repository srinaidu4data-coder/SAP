"""Mission-critical precision unit tests — NASA/SpaceX fail-closed bar."""

from __future__ import annotations

import json

import pytest

from sapilot.autobot.digital_twin import DigitalTwin
from sapilot.know.gather import ScenarioDataGatherer
from sapilot.autobot.consultant import ALL_MISSIONS
from sapilot.mission.precision import (
    JournalHashChain,
    MissionAbort,
    MissionGate,
    PACK_EXACT,
    PTP_EXACT,
    amount_equal,
    assert_never_tcode_in_data_field,
    is_tcode_command,
    manifest_hash,
    scan_rows_for_tcode_pollution,
    verify_document_chain_invariants,
    verify_exact,
    verify_pack_exact,
)


def test_never_tcode_in_lifnr():
    with pytest.raises(MissionAbort):
        assert_never_tcode_in_data_field("LIFNR", "/nF110")
    with pytest.raises(MissionAbort):
        assert_never_tcode_in_data_field("SUPPLIER", "/oME23N")
    assert_never_tcode_in_data_field("LIFNR", "0000100001")  # no raise
    assert_never_tcode_in_data_field("EBELN", "4500000001")


def test_is_tcode_command():
    assert is_tcode_command("/nF110")
    assert is_tcode_command("/OF110")
    assert not is_tcode_command("0000100001")
    assert not is_tcode_command("4500000001")
    assert not is_tcode_command("")


def test_verify_exact_sap_keys():
    errs = verify_exact({"LIFNR": "0000100001"}, {"LIFNR": "100001"}, normalize_sap_key=True)
    assert errs == []


def test_amount_equal():
    assert amount_equal("1250.00", "1250")
    assert amount_equal("1250.00", "1250.0")
    assert not amount_equal("1250.00", "1250.01")


def test_empty_gate_is_nogo():
    """Fail closed: empty criteria board is NOT a go."""
    g = MissionGate("TEST")
    assert g.is_go() is False
    with pytest.raises(MissionAbort):
        g.abort_if_nogo()


def test_gate_blocks_on_fail():
    g = MissionGate("TEST")
    g.require("a", True, "ok")
    g.require("b", False, "broken")
    assert g.is_go() is False
    with pytest.raises(MissionAbort):
        g.abort_if_nogo()


def test_all_fleet_packs_have_fingerprints():
    for m in ALL_MISSIONS:
        assert m["pack"] in PACK_EXACT, f"missing fingerprint for {m['pack']}"
    assert len(ALL_MISSIONS) == 22
    assert len(PACK_EXACT) >= 22


def test_all_fleet_fingerprints_match_twin():
    twin = DigitalTwin()
    twin.ensure_po_chain()
    twin.ensure_otc_chain()
    twin.ensure_vendor_payment_ready()
    twin.ensure_customer_payment_ready()
    twin.ensure_abap_debug_ready()
    g = ScenarioDataGatherer(twin.rfc)
    failures = []
    for m in ALL_MISSIONS:
        pack = g.gather(m["pack"])
        errs = verify_pack_exact(pack.tables, PACK_EXACT[m["pack"]])
        if errs:
            failures.append(f"{m['id']}: {errs}")
        if not pack.ready:
            failures.append(f"{m['id']}: not ready {pack.summary}")
    assert failures == [], failures


def test_ptp_po_fingerprint():
    twin = DigitalTwin()
    pack = ScenarioDataGatherer(twin.rfc).gather("ptp_06_purchase_order")
    errs = verify_pack_exact(pack.tables, PTP_EXACT["ptp_06_purchase_order"])
    assert errs == [], errs


def test_otc_so_fingerprint():
    twin = DigitalTwin()
    pack = ScenarioDataGatherer(twin.rfc).gather("otc_05_sales_order")
    errs = verify_pack_exact(pack.tables, PTP_EXACT["otc_05_sales_order"])
    assert errs == [], errs


def test_document_chain_invariants():
    twin = DigitalTwin()
    twin.ensure_po_chain()
    twin.ensure_otc_chain()
    errs = verify_document_chain_invariants(twin)
    assert errs == [], errs


def test_pollution_scan_detects_tcode():
    class FakeSlice:
        def __init__(self, rows):
            self.rows = rows

    polluted = scan_rows_for_tcode_pollution(
        {"LFA1": FakeSlice([{"LIFNR": "/nF110"}])}
    )
    assert polluted
    clean = scan_rows_for_tcode_pollution(
        {"LFA1": FakeSlice([{"LIFNR": "0000100001"}])}
    )
    assert clean == []


def test_hash_chain_detects_tamper(tmp_path):
    p = tmp_path / "chain.jsonl"
    c = JournalHashChain(p)
    c.append("a", {"x": 1})
    c.append("b", {"y": 2})
    ok, errs = c.verify_chain()
    assert ok and not errs
    lines = p.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace('"x": 1', '"x": 99')
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok2, errs2 = JournalHashChain(p).verify_chain()
    assert not ok2
    assert errs2


def test_hash_chain_sequence(tmp_path):
    p = tmp_path / "chain.jsonl"
    c = JournalHashChain(p)
    c.append("a", 1)
    c.append("b", 2)
    c.append("c", 3)
    ok, errs = c.verify_chain()
    assert ok, errs
    lines = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert [r["seq"] for r in lines] == [1, 2, 3]


def test_manifest_hash_stable():
    h1 = manifest_hash()
    h2 = manifest_hash()
    assert h1 == h2
    assert len(h1) == 64


def test_executor_blocks_tcode_in_data_field():
    """Grounded executor choke-point refuses /nTCODE into non-okcd fields."""
    from sapilot.act.executor import GroundedExecutor
    from sapilot.connect.gui import MockGuiSession
    from sapilot.policy.tier import TierContext
    from sapilot.schemas import (
        Action,
        ActionType,
        GuiElement,
        ObservationStatus,
        PlannedStep,
        ScreenSnapshot,
        Tier,
    )

    snap = ScreenSnapshot(
        tcode="XK03",
        title="Vendor",
        elements=GuiElement(
            id="wnd[0]",
            type="GuiMainWindow",
            children=[
                GuiElement(
                    id="wnd[0]/usr/ctxtRF02K-LIFNR",
                    type="GuiCTextField",
                    name="RF02K-LIFNR",
                    changeable=True,
                ),
            ],
        ),
    )
    gui = MockGuiSession(screens={"XK03": snap}, initial="XK03")
    gui.tcode = "XK03"
    ex = GroundedExecutor(TierContext(Tier.T1_SANDBOX, "100", "D"), gui=gui)
    step = PlannedStep(
        assessment="fill vendor",
        gap="need lifnr",
        action=Action(
            type=ActionType.SET_TEXT,
            target="wnd[0]/usr/ctxtRF02K-LIFNR",
            value="/nF110",
        ),
        justification_ref="precision:block_tcode",
        confidence=0.9,
    )
    obs = ex.execute(step)
    assert obs.status == ObservationStatus.POLICY_VIOLATION
    assert "tcode" in (obs.policy_reason or "") or "PRECISION" in (obs.message or "")
