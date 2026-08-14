"""Opened-table content analysis. F7 is the count; F8 rows are the story."""

from sapilot.product.table_read import analyze_grid, words_to_rows


def test_analyze_vbak_sample():
    rec = analyze_grid(
        "VBAK",
        [
            ["VBELN", "AUART", "VKORG", "ERDAT"],
            ["000001", "OR", "1710", "20240115"],
            ["000002", "OR", "1710", "20240116"],
            ["000003", "RE", "1710", "20240117"],
        ],
        12255,
    )
    assert rec["visible_rows"] == 3
    assert "12,255" in rec["story"] or "12255" in rec["story"].replace(",", "")
    assert "sample" in rec["story"].lower()
    assert rec["columns"][0] == "VBELN"


def test_empty_table_story():
    rec = analyze_grid("FARR_D_POB", [["CLIENT", "POB_ID"]], 0)
    assert "empty" in rec["story"].lower() or "0" in rec["story"]


def test_words_to_rows_groups_by_y():
    class W:
        def __init__(self, text, x, ry):
            self.text = text
            self.x = x
            self.ry = ry
            self.y = int(ry * 100)

        def in_chrome(self):
            return False

    rows = words_to_rows([W("AUART", 10, 0.30), W("OR", 10, 0.40), W("VKORG", 80, 0.30)])
    assert any("AUART" in r and "VKORG" in r for r in rows)
