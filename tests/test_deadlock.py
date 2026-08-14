"""A stuck step must return, not own the glass forever."""

import time

from sapilot.product.deadlock import run_cut


def test_run_cut_returns_on_timeout():
    def hang():
        time.sleep(8)
        return "never"

    rec = run_cut(hang, 0.4, on_cut={"cut": True, "ok": False})
    assert rec["cut"] is True
    assert rec["ok"] is False


def test_run_cut_returns_value_when_fast():
    rec = run_cut(lambda: {"ok": True, "title": "SE16N"}, 2, on_cut={"cut": True})
    assert rec["ok"] is True
    assert rec["title"] == "SE16N"
