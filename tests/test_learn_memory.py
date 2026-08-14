"""Self-learning memory prefers wins and seeds YouTube/community recipes."""

from sapilot.learn.ingest import seed
from sapilot.learn.memory import NavMemory
from sapilot.learn.policy import remember, signature, suggest


def test_signature_stable():
    a = signature("General Table Display", "Unit VBA is not created in language EN", "", "focus_database")
    b = signature("General Table Display", "Unit VBA is not created in language EN", "", "focus_database")
    assert a == b
    assert "unit_lang" in a
    assert "focus_database" in a


def test_memory_prefers_winning_click(tmp_path):
    mem = NavMemory(tmp_path / "nav.db")
    sig_title = "General Table Display"
    remember(sig_title, "", "", "focus_database", {"kind": "click", "rx": 0.9, "ry": 0.9}, -1, mem=mem)
    remember(sig_title, "", "", "focus_database", {"kind": "click", "rx": 0.30, "ry": 0.248}, 1, mem=mem)
    remember(sig_title, "", "", "focus_database", {"kind": "click", "rx": 0.30, "ry": 0.248}, 1, mem=mem)
    hit = mem.best_action(signature(sig_title, "", "", "focus_database"), "focus_database")
    assert hit is not None
    assert hit["rx"] == 0.30


def test_seed_has_youtube_and_f7(tmp_path, monkeypatch):
    mem = NavMemory(tmp_path / "nav.db")
    monkeypatch.setattr("sapilot.learn.ingest.default_memory", lambda: mem)
    monkeypatch.setattr("sapilot.learn.policy.default_memory", lambda: mem)
    rec = seed(mem)
    assert rec["recipes"] >= 6
    assert mem.stats()["knowledge"] >= 6
    titles = " ".join(k["title"] for k in mem.knowledge())
    assert "YouTube" in titles or "ERP UP" in titles or "SE16" in titles
    act = suggest("General Table Display", "", "", "count", mem=mem)
    assert act is not None
    assert act.get("name") == "F7" or act.get("kind") == "key"
