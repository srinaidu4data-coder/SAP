"""ALV grid extraction including traffic-light cell state."""

from __future__ import annotations

from typing import Any

from sapilot.schemas import GuiElement


def extract_alv_from_tree(root: GuiElement) -> list[dict[str, Any]]:
    """
    Walk serialized tree for GuiShell / grid-like nodes and extract textual cells.
    Live COM path may enrich via .GetCellValue when session available.
    """
    grids: list[dict[str, Any]] = []

    def walk(el: GuiElement) -> None:
        if el.type in {"GuiShell", "GuiTableControl"} or "grid" in el.name.lower():
            cells = []
            for child in el.children:
                cells.append(
                    {
                        "id": child.id,
                        "text": child.text,
                        "name": child.name,
                        "type": child.type,
                        "traffic_light": _traffic_from_text(child.text, child.extra),
                    }
                )
            grids.append({"id": el.id, "name": el.name, "cells": cells})
        for c in el.children:
            walk(c)

    walk(root)
    return grids


def _traffic_from_text(text: str, extra: dict[str, Any]) -> str | None:
    if extra.get("traffic_light"):
        return str(extra["traffic_light"])
    t = (text or "").lower()
    if t in {"1", "red", "error"}:
        return "red"
    if t in {"2", "yellow", "warning"}:
        return "yellow"
    if t in {"3", "green", "ok", "success"}:
        return "green"
    return None


def extract_alv_live(session: Any, shell_id: str) -> list[dict[str, Any]]:
    """Best-effort live ALV via GuiShell grid methods."""
    try:
        grid = session.FindById(shell_id)
        row_count = int(grid.RowCount)
        col_count = int(grid.ColumnCount)
        rows = []
        for r in range(min(row_count, 500)):
            row = {"row": r, "cells": []}
            for c in range(min(col_count, 50)):
                try:
                    val = grid.GetCellValue(r, grid.ColumnOrder(c))
                except Exception:
                    val = ""
                row["cells"].append({"col": c, "value": str(val)})
            rows.append(row)
        return rows
    except Exception:
        return []
