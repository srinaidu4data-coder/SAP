"""Where to type the table name on SE16N (Belize / dark theme).

OCR on this book never reads the 'Data base:' label. It does read
'Text Table:' on the next row. Data base is one row above that, same column.
After /nSE16N the caret is already in Data base — type first, click only if needed.
"""
from __future__ import annotations

from sapilot.autobot.eyes import find_label

# Row gap on Belize SE16N header (Text Table sits under Data base).
_ROW = 0.045
# Horizontal center of the Data base edit (right of the label).
_FIELD_RX = 0.30


def locate_database(words) -> tuple[float, float, str]:
    """Return (rx, ry, how) for the Data base input."""
    if not words:
        return _FIELD_RX, 0.215, "default"

    # Never use fuzzy find_label('Data base') — it matched '= A' on this theme.
    text_table = None
    ordered = sorted(words, key=lambda w: (w.y, w.x))
    for i, w in enumerate(ordered[:-1]):
        a = (w.text or "").strip().lower()
        b = (ordered[i + 1].text or "").strip().lower()
        if a == "text" and b.startswith("table"):
            text_table = ordered[i + 1]
            break
    if text_table is None:
        text_table = find_label(words, ["Text Table"])
        if text_table is not None and "text" not in (text_table.text or "").lower():
            # reject a lone fuzzy 'Table'
            if (text_table.text or "").lower().strip() in {"table", "table:"}:
                text_table = None

    if text_table is not None and 0.18 <= text_table.ry <= 0.36:
        rx = max(_FIELD_RX, min(0.40, text_table.right_rx + 0.08))
        ry = max(0.18, text_table.ry - _ROW)
        return rx, ry, "above_text_table"

    hits = find_label(words, ["Max. Number of Hits", "Number of Hits"])
    if hits is not None and 0.28 <= hits.ry <= 0.42:
        return _FIELD_RX, max(0.18, hits.ry - 2 * _ROW), "above_max_hits"

    # Strict Data base only (exact-ish), never short 'base'
    for w in words:
        t = (w.text or "").strip().lower().replace(":", "")
        if t in {"data base", "database"} and 0.16 <= w.ry <= 0.34:
            return min(0.40, w.right_rx + 0.10), w.ry, "ocr_data_base"

    return _FIELD_RX, 0.215, "default"
