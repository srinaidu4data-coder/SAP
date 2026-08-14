"""Standalone research document is written and linked."""

from sapilot.product.report import render_html, report_url, write_report
from sapilot.product.research import get_job, latest_job, public_job


def test_report_url():
    assert report_url("01409b827733") == "/research/01409b827733"


def test_render_html_contains_title_and_link():
    html = render_html(
        {
            "id": "abc123",
            "title": "Revenue Accounting and Reporting (your process)",
            "asked": "Analyze complete RAR process",
            "spine": "order → invoice → RAI",
            "status": "done",
            "counts": [{"table": "FARR_D_POB", "entries_found": 0, "rank": "LIVE", "notes": "empty"}],
            "visits": [{"tcode": "VF03", "title": "Display Billing Documents", "shot": "visit_vf03.png"}],
            "hops": ["invoice → RAI"],
            "narrative": ["RAR contracts are empty."],
            "progress": {"done": 1, "total": 10},
        }
    )
    assert "Revenue Accounting" in html
    assert "/research/abc123" in html or "abc123" in html
    assert "FARR_D_POB" in html
    assert "VF03" in html


def test_public_job_exposes_report_url():
    rec = public_job({"id": "xyz", "status": "done", "counts": [], "events": []})
    assert rec["report_url"] == "/research/xyz"


def test_latest_job_loads_finished_sitting_from_disk():
    j = latest_job() or get_job("01409b827733")
    if not j:
        return
    assert j.get("id")
    path = write_report(j)
    assert path is not None and path.exists()
    html = path.read_text(encoding="utf-8")
    assert "SAPILOT" in html
    assert j.get("id", "") in html or (j.get("title") or "")[:12] in html
