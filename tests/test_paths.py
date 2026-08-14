"""A failed table must open a different door, not the same key again."""

from sapilot.learn.paths import abandon_family, drop_family, next_paths


def test_farr_revenue_next_is_not_farr_revenue():
    alts = next_paths("FARR_D_REVENUE", {"FARR_D_REVENUE"})
    assert "FARR_D_REVENUE" not in alts
    assert "DD02L" in alts
    assert "VBRK" in alts or "VBREVE" in alts


def test_does_not_repeat_already_seen():
    alts = next_paths("FARR_D_REVENUE", {"FARR_D_REVENUE", "DD02L", "VBRK", "VBREVE"})
    assert "DD02L" not in alts
    assert "VBRK" not in alts


def test_two_farr_misses_abandons_the_family():
    counts = [
        {"table": "FARR_D_REVENUE", "rank": "ABSENT", "notes": "does not exist"},
        {"table": "FARR_D_FULFILL", "rank": "ABSENT", "notes": "does not exist"},
    ]
    assert abandon_family(counts, "FARR") is True
    q = drop_family(
        ["FARR_D_INV_ITM", "FARR_D_BILLING", "VBRK", "FARR_D_CONTRACT"],
        "FARR",
        ["FARR_D_CONTRACT"],
    )
    assert "FARR_D_INV_ITM" not in q
    assert "FARR_D_BILLING" not in q
    assert "VBRK" in q
    assert "FARR_D_CONTRACT" in q
