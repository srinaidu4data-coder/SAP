"""SE16N Data base field is scored separately from the command field and the ALV."""

from sapilot.connect.hwnd_input import (
    ChildInfo,
    Rect,
    pick_database,
    pick_okcd,
    score_database_candidate,
)


def _child(*, hwnd=1, cls="Edit", box=(220, 170, 420, 196), acc="", title=""):
    return ChildInfo(
        hwnd=hwnd,
        class_name=cls,
        title=title,
        rect=Rect(*box),
        acc_name=acc,
    )


def test_database_named_field_wins():
    parent = Rect(0, 0, 1000, 800)
    db = _child(acc="Data base", box=(220, 180, 430, 204))
    assert score_database_candidate(db, parent) >= 60
    assert pick_database([db], parent) is db


def test_okcd_is_not_the_database_field():
    parent = Rect(0, 0, 1000, 800)
    okcd = _child(hwnd=2, acc="Command Field", box=(20, 10, 180, 32))
    db = _child(hwnd=3, acc="Data base", box=(220, 180, 430, 204))
    assert pick_okcd([okcd, db], parent) is okcd
    assert pick_database([okcd, db], parent, okcd_hwnd=2) is db


def test_alv_cell_is_not_database():
    parent = Rect(0, 0, 1000, 800)
    alv = _child(hwnd=4, acc="Unit", box=(240, 420, 320, 442))
    assert pick_database([alv], parent) is None


def test_locate_uses_text_table_row_not_fuzzy_data_base():
    from sapilot.autobot.eyes import WordBox
    from sapilot.product.se16n_field import locate_database

    def box(text, x, y, w=40, h=14, iw=1942, ih=1150):
        return WordBox(text=text, x=x, y=y, w=w, h=h, conf=90, img_w=iw, img_h=ih)

    # Same OCR as the live Belize shot: no 'Data base', garbage '= A', plus Text Table.
    words = [
        box("= A", 1117, 158, 218, 14),
        box("Text", 252, 297, 40, 16),
        box("Table:", 307, 297, 50, 16),
        box("Hits:", 312, 392, 40, 16),
    ]
    rx, ry, how = locate_database(words)
    assert how == "above_text_table"
    assert 0.18 <= ry <= 0.26
    assert 0.24 <= rx <= 0.42


def test_toolbar_edit_is_not_database():
    parent = Rect(0, 0, 1000, 800)
    toolbar = _child(hwnd=5, acc="", box=(20, 10, 180, 32))
    db = _child(hwnd=6, acc="Data base", box=(220, 180, 430, 204))
    assert pick_database([toolbar, db], parent) is db
