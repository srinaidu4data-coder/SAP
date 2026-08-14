"""Public SAP navigation knowledge: tutorials, community, YouTube recipes.

We do not download video files. We store the same steps those videos teach
(command field, /n, F3 back, F12 cancel, SE16N Number of Entries / F7)
and turn them into skills the glass can overwrite.
"""
from __future__ import annotations

from typing import Any

from sapilot.learn.memory import NavMemory, default_memory
from sapilot.learn.policy import remember

# YouTube + community recipes (titles/URLs are public; steps are the taught procedure).
YOUTUBE_RECIPES: list[dict[str, Any]] = [
    {
        "source": "youtube",
        "url": "https://www.youtube.com/watch?v=yesk7pEZPL8",
        "title": "Command field / OK-code — ERP UP",
        "intent": "goto",
        "steps": [
            "Click only the command field (OK-code), never a dynpro body field",
            "Type the t-code, or /nTCODE to jump from inside another transaction",
            "Enter. Do not type t-codes into Supplier / table selection cells",
        ],
        "action": {"kind": "goto", "tcode": "SE16N"},
    },
    {
        "source": "youtube",
        "url": "https://www.youtube.com/watch?v=gSP9_IPGTvY",
        "title": "SAP ERP / S/4 navigation overview — ERP UP",
        "intent": "recover",
        "steps": [
            "F3 = Back without save",
            "F12 = Cancel",
            "Easy Access is the home screen after enough Backs or /n",
        ],
        "action": {"kind": "back_out"},
    },
    {
        "source": "youtube",
        "url": "https://www.youtube.com/watch?v=gjveBQnWnME",
        "title": "Data Browser SE16 / SE16N / SE16H — ERP UP",
        "intent": "focus_database",
        "steps": [
            "SE16N = General Table Display",
            "Type the table name in Data base, not in Selection Criteria",
            "Enter to load fields, then Number of Entries (not the 500 list)",
        ],
        "action": {"kind": "click", "rx": 0.30, "ry": 0.248},
    },
    {
        "source": "youtube",
        "url": "https://www.youtube.com/watch?v=PG86bU3YJa8",
        "title": "SE16 useful functions — number of entries — ERP UP",
        "intent": "count",
        "steps": [
            "To count under current selection: Number of Entries",
            "That is F7. F8 / List Output is a 500-row dump, not a census",
        ],
        "action": {"kind": "key", "name": "F7"},
    },
    {
        "source": "youtube",
        "url": "https://www.youtube.com/watch?v=QaTEQTAxtB4",
        "title": "Count table entries SE16H — Sampath Kumar",
        "intent": "count",
        "steps": ["Count is a dedicated function, not reading the ALV length."],
        "action": {"kind": "key", "name": "F7"},
    },
    {
        "source": "web",
        "url": "https://community.sap.com/t5/application-development-discussions/get-se16-count/td-p/6575179",
        "title": "SAP Community — SE16 count = Number of Entries / F7",
        "intent": "count",
        "steps": ["Ctrl+F then F7 / Number of Entries is the count, not SELECT *."],
        "action": {"kind": "key", "name": "F7"},
    },
    {
        "source": "web",
        "url": "https://success.panaya.com/docs/sap-gui-supported-special-keys-shortcuts",
        "title": "SAP GUI special keys — F3 back, F12 cancel",
        "intent": "recover",
        "steps": ["F3 Back exits without saving. F12 Cancel. Never F11 from this wing."],
        "action": {"kind": "back_out"},
    },
    {
        "source": "web",
        "url": "https://www.reddit.com/r/SAP/comments/d2nqkd/what_is_behind_number_of_entries_in_se16n/",
        "title": "r/SAP — what Number of Entries actually does",
        "intent": "count",
        "steps": ["Number of Entries runs a count, not a list."],
        "action": {"kind": "key", "name": "F7"},
    },
]


def seed(mem: NavMemory | None = None) -> dict[str, int]:
    """Load tutorial recipes into knowledge + prior skills."""
    mem = mem or default_memory()
    n = 0
    for rec in YOUTUBE_RECIPES:
        mem.add_knowledge(rec["source"], rec["title"], rec, url=rec.get("url") or "")
        intent = rec.get("intent") or "goto"
        action = rec.get("action") or {}
        # Priors: two synthetic wins so the glass uses them until a live loss.
        remember(
            "General Table Display" if intent != "menu" else "SAP Easy Access",
            "",
            "",
            intent,
            action,
            reward=1,
            note=f"seed:{rec['source']}",
            mem=mem,
        )
        remember(
            "General Table Display" if intent != "menu" else "SAP Easy Access",
            "",
            "",
            intent,
            action,
            reward=1,
            note=f"seed:{rec['source']}",
            mem=mem,
        )
        n += 1
    return {"recipes": n, **mem.stats()}


def ingest_web(mem: NavMemory | None = None) -> dict[str, Any]:
    """Refresh seed and try to fetch public page titles (optional network)."""
    mem = mem or default_memory()
    seeded = seed(mem)
    fetched = 0
    errors: list[str] = []
    try:
        import urllib.request

        for rec in YOUTUBE_RECIPES:
            url = rec.get("url") or ""
            if not url.startswith("http"):
                continue
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "SAPILOT-learn/1.0"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    body = r.read(800).decode("utf-8", errors="ignore")
                if body:
                    fetched += 1
                    mem.add_knowledge(
                        rec["source"] + "+fetch",
                        rec["title"],
                        {**rec, "fetched": True, "bytes": len(body)},
                        url=url,
                    )
            except Exception as e:
                errors.append(f"{url}: {e}"[:160])
    except Exception as e:
        errors.append(str(e)[:160])
    return {"ok": True, "seeded": seeded, "fetched": fetched, "errors": errors[:8], **mem.stats()}
