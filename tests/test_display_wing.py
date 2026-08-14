"""Display wing: create t-codes refused; every catalog step is display-safe."""

from __future__ import annotations

import pytest

from sapilot.display.catalog import CYCLES, get_cycle
from sapilot.display.policy import (
    DisplayPolicyError,
    assert_display_tcode,
    is_create_screen,
    is_display_screen,
    remap_to_display,
)
from sapilot.display.walker import _title_matches, plan


@pytest.mark.parametrize(
    "bad",
    [
        "ME21N",
        "ME51N",
        "VA01",
        "VL01N",
        "VF01",
        "MIGO",
        "MIRO",
        "FB50",
        "FB01",
        "CK11N",
        "CK24",
        "CO01",
        "MM01",
        "XK01",
        "SM30",
        "SPRO",
        "SE38",
        "F110",
        "FTR_CREATE",
        "BP",
    ],
)
def test_create_change_post_refused(bad: str):
    with pytest.raises(DisplayPolicyError) as ei:
        assert_display_tcode(bad)
    assert bad in str(ei.value) or "refuses" in str(ei.value).lower() or "fail-closed" in str(ei.value).lower()


@pytest.mark.parametrize(
    "good",
    ["ME23N", "ME53N", "VA03", "VL03N", "VF03", "MM03", "XK03", "MB03", "MIR4", "FB03", "CK13N", "CO03", "KS03", "SE16N", "FBL1N", "FBL5N", "CKM3N"],
)
def test_display_allowed(good: str):
    assert assert_display_tcode(good) == good


def test_remap_is_suggestion_not_an_open():
    assert remap_to_display("ME21N") == "ME23N"
    assert remap_to_display("MIGO") == "MB03"
    assert remap_to_display("MIRO") == "MIR4"
    # remap must not authorize opening the create t-code
    with pytest.raises(DisplayPolicyError):
        assert_display_tcode("ME21N")


def test_create_screen_detector():
    assert is_create_screen("Create Purchase Order")
    assert is_create_screen("Enter Incoming Invoice")
    assert is_create_screen("Goods Receipt Purchase Order")
    assert is_create_screen("Create Sales Order")
    assert not is_create_screen("Display Purchase Order")
    assert not is_create_screen("Stock Transp. Order 100011 Created by pranali")
    assert not is_create_screen("General Table Display")
    assert not is_create_screen("Display Material")
    assert is_display_screen("Display Purchase Order 4500000002")
    assert is_display_screen("General Table Display")


def test_every_catalog_step_is_display_safe():
    for name, cycle in CYCLES.items():
        planned = plan(name)
        assert planned.name == name
        for step in cycle.steps:
            assert assert_display_tcode(step.tcode) == step.tcode


def test_unknown_tcode_fail_closed():
    with pytest.raises(DisplayPolicyError):
        assert_display_tcode("Z invent")
    with pytest.raises(DisplayPolicyError):
        assert_display_tcode("OKKN")


def test_plan_without_name_is_all_examples():
    from sapilot.display.catalog import CYCLES
    from sapilot.display.walker import plan

    for name in CYCLES:
        assert plan(name).name == name


def test_get_cycle_unknown():
    with pytest.raises(KeyError):
        get_cycle("not-a-cycle")


def test_me23n_does_not_match_purchase_req_title():
    step = get_cycle("ptp").steps[4]  # ME23N
    assert step.tcode == "ME23N"
    assert not _title_matches(step, "Display Purchase Req.")
    assert _title_matches(step, "Stock Transp. Order 100011 Created by pranali")
    assert _title_matches(step, "Display Purchase Order")


def test_cycles_are_generic_examples_not_the_product():
    # Product is the spine + policy. Named cycles are examples.
    assert set(CYCLES) >= {"ptp", "otc", "copc", "r2r", "collections"}
    for c in CYCLES.values():
        assert "example" in c.title.lower() or c.name in {"ptp", "otc", "copc", "r2r", "collections"}
