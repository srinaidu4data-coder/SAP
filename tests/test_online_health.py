"""Online health probes must never hang tests."""

from __future__ import annotations

from sapilot.autobot.online_health import OnlineHealth, probe_online_health, run_with_timeout


def test_run_with_timeout_ok():
    ok, val, err = run_with_timeout(lambda: 42, timeout_s=1.0)
    assert ok and val == 42 and err == ""


def test_run_with_timeout_raises():
    def boom():
        raise ValueError("x")

    ok, val, err = run_with_timeout(boom, timeout_s=1.0)
    assert not ok
    assert "ValueError" in err


def test_probe_returns_health():
    h = probe_online_health(com_timeout_s=2.0)
    assert isinstance(h, OnlineHealth)
    assert 0.0 <= h.score <= 1.0
    assert isinstance(h.blockers, list)
