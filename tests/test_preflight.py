from __future__ import annotations

from sapilot.preflight import run_preflight


def test_preflight_hard_checks_pass():
    results = run_preflight(strict=False)
    by_id = {r["id"]: r for r in results}
    assert by_id["python"]["ok"]
    assert by_id["policy"]["ok"]
    assert by_id["denylist"]["ok"]
