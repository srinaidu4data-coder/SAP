"""
Eyes — screenshot, OCR, regions, status bar. No SAP GUI Scripting.

A human looks at the window, reads labels, and reads the green/red bar at
the bottom. This module does the same from pixels.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WordBox:
    text: str
    x: int
    y: int
    w: int
    h: int
    conf: float
    img_w: int
    img_h: int

    @property
    def rx(self) -> float:
        return (self.x + self.w / 2) / max(self.img_w, 1)

    @property
    def ry(self) -> float:
        return (self.y + self.h / 2) / max(self.img_h, 1)

    @property
    def right_rx(self) -> float:
        return min(0.97, (self.x + self.w + 18) / max(self.img_w, 1))

    @property
    def left_rx(self) -> float:
        return max(0.02, (self.x - 18) / max(self.img_w, 1))

    @property
    def below_ry(self) -> float:
        return min(0.97, (self.y + self.h + 14) / max(self.img_h, 1))

    def in_chrome(self) -> bool:
        """Menu / title (top) and status strip (bottom) are not field labels."""
        return self.ry < 0.10 or self.ry > 0.93


@dataclass
class StatusRead:
    raw: str
    kind: str  # S | E | W | I | A | ""
    text: str
    docno: str | None = None


@dataclass
class ScreenView:
    path: str
    width: int
    height: int
    words: list[WordBox] = field(default_factory=list)
    status: StatusRead | None = None


# ---------------------------------------------------------------------------
# OCR backends
# ---------------------------------------------------------------------------


_TESSERACT_CANDIDATES = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


def configure_tesseract() -> str | None:
    """Point pytesseract at a real binary. PATH is often stale after install."""
    import os
    import shutil

    try:
        import pytesseract  # type: ignore
    except Exception:
        return None
    override = os.environ.get("SAPILOT_TESSERACT") or os.environ.get("TESSERACT_CMD")
    candidates = [override] if override else []
    found = shutil.which("tesseract")
    if found:
        candidates.append(found)
    candidates.extend(_TESSERACT_CANDIDATES)
    for path in candidates:
        if path and Path(path).is_file():
            pytesseract.pytesseract.tesseract_cmd = path
            try:
                pytesseract.get_tesseract_version()
                return path
            except Exception:
                continue
    return None


def ocr_available() -> str | None:
    exe = configure_tesseract()
    return exe if exe else None


def ocr_words(image: Any) -> list[WordBox]:
    """Return word boxes in image-pixel coords. Empty if no OCR engine."""
    try:
        import pytesseract  # type: ignore
        from PIL import Image

        if not configure_tesseract():
            return []
        if not isinstance(image, Image.Image):
            image = Image.open(image)
        img = image.convert("RGB")
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except Exception as e:
        log.debug("OCR unavailable: %s", e)
        return []
    w0, h0 = img.size
    out: list[WordBox] = []
    n = len(data.get("text") or [])
    for i in range(n):
        raw = (data["text"][i] or "").strip()
        if not raw:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf >= 0 and conf < 35:
            continue
        out.append(
            WordBox(
                text=raw,
                x=int(data["left"][i]),
                y=int(data["top"][i]),
                w=int(data["width"][i]),
                h=int(data["height"][i]),
                conf=conf,
                img_w=w0,
                img_h=h0,
            )
        )
    return out


def ocr_text(image: Any) -> str:
    words = ocr_words(image)
    return " ".join(w.text for w in words)


# ---------------------------------------------------------------------------
# Status bar (human reads the strip at the bottom)
# ---------------------------------------------------------------------------

_DOCNO = re.compile(
    r"\b((?:45|41|32|10)\d{8}|\d{8,12})\b"
)
_KIND = re.compile(r"^\s*([SEWIA])\s+(.+)$", re.I)


def parse_status_bar(raw: str) -> StatusRead:
    text = (raw or "").strip()
    text = re.sub(r"\s+", " ", text)
    kind = ""
    body = text
    m = _KIND.match(text)
    if m:
        kind = m.group(1).upper()
        body = m.group(2).strip()
    lower = body.lower()
    if not kind:
        if "no values found" in lower or "does not exist" in lower or "not possible" in lower:
            kind = "E"
        elif "created" in lower or "displayed" in lower or "saved" in lower:
            kind = "S"
    docno = None
    dm = _DOCNO.search(body)
    if dm:
        docno = dm.group(1)
    return StatusRead(raw=text, kind=kind, text=body, docno=docno)


def crop_status_bar(image: Any) -> Any:
    from PIL import Image

    if not isinstance(image, Image.Image):
        image = Image.open(image)
    w, h = image.size
    top = int(h * 0.935)
    return image.crop((0, top, w, h))


def read_status(image: Any) -> StatusRead:
    return parse_status_bar(ocr_text(crop_status_bar(image)))


# ---------------------------------------------------------------------------
# Label find — "click the box to the right of this word"
# ---------------------------------------------------------------------------


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def find_label(words: list[WordBox], aliases: list[str]) -> WordBox | None:
    """Best word/phrase match for a human-readable field label.

    Skips the menu and status strip. Prefers an exact / longer alias so
    "Purchase" does not steal a click meant for "Purchasing Doc".
    """
    if not words:
        return None
    want = [(a, _norm(a)) for a in aliases if a and _norm(a)]
    want.sort(key=lambda t: len(t[1]), reverse=True)
    usable = [w for w in words if not w.in_chrome()]
    if not usable:
        usable = list(words)

    def _score(nw: str, a: str) -> int:
        if nw == a:
            return 100 + len(a)
        if len(a) >= 6 and a in nw:
            return 80 + len(a)
        if len(a) >= 6 and nw in a:
            return 60 + len(nw)
        if len(a) >= 4 and (a in nw or nw in a):
            return 40 + min(len(a), len(nw))
        return 0

    best: tuple[int, WordBox] | None = None
    for w in usable:
        nw = _norm(w.text)
        for _, a in want:
            sc = _score(nw, a)
            if sc and (best is None or sc > best[0]):
                best = (sc, w)
    ordered = sorted(usable, key=lambda w: (w.y, w.x))
    for i, w in enumerate(ordered[:-1]):
        nxt = ordered[i + 1]
        if abs(w.y - nxt.y) > max(w.h, nxt.h):
            continue
        if nxt.x < w.x:
            continue
        joined = _norm(w.text + nxt.text)
        box = WordBox(
            text=f"{w.text} {nxt.text}",
            x=w.x,
            y=min(w.y, nxt.y),
            w=nxt.x + nxt.w - w.x,
            h=max(w.h, nxt.h),
            conf=min(w.conf, nxt.conf),
            img_w=w.img_w,
            img_h=w.img_h,
        )
        for _, a in want:
            sc = _score(joined, a) + 5
            if sc and (best is None or sc > best[0]):
                best = (sc, box)
    return best[1] if best else None


def click_point_for_label(label: WordBox, *, side: str = "right") -> tuple[float, float]:
    """Where a human would click the input next to a label."""
    if side == "below":
        return label.rx, label.below_ry
    if side == "left":
        return label.left_rx, label.ry
    if side == "on":
        return label.rx, label.ry
    return min(0.96, label.right_rx + 0.02), label.ry


def parse_hit_count(words: list[WordBox], status: StatusRead | None = None) -> int | None:
    """SE16N 'Number of Hits: N' / '1 Entry found'. None if the screen has no count."""
    blob = " ".join(w.text for w in words)
    if status and status.text:
        blob = f"{blob} {status.text}"
    m = re.search(r"(?:number of\s+)?hits\s*[:\-]?\s*(\d+)", blob, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s+entr(?:y|ies)\s+found", blob, re.I)
    if m:
        return int(m.group(1))
    for w in words:
        if _norm(w.text) in {"hits", "hit"}:
            for n in words:
                if n.text.isdigit() and abs(n.ry - w.ry) < 0.04 and n.rx > w.rx - 0.02:
                    return int(n.text)
    return None


def proof_from_view(view: ScreenView, value: str) -> tuple[bool, str]:
    """
    A table prove is true only when the key is on a filtered result.
    500-hit dumps (filter never applied) are not proof even if OCR saw the key.
    """
    blob = " ".join(w.text for w in view.words).lower()
    status_txt = (view.status.text if view.status else "").lower()
    if "no values found" in blob or "no values found" in status_txt:
        return False, "No values found. Not created."
    hits = parse_hit_count(view.words, view.status)
    seen = words_contain(view.words, value)
    if hits is not None and hits >= 50:
        return False, f"{hits} hits — filter did not apply. Not proven."
    if hits == 0:
        return False, "0 hits. Not created."
    if hits == 1 and seen:
        return True, f"1 hit, table contains {value}"
    if hits is not None and 1 < hits < 50 and seen:
        return True, f"{hits} hits, table contains {value}"
    # No hit count → we are not on a SE16N result. A document display that
    # happens to show the number is not a table prove.
    return False, f"table has no proven row for {value} (hits={hits})."


def words_contain(words: list[WordBox], needle: str, *, region: tuple[float, float, float, float] | None = None) -> bool:
    n = _norm(needle)
    if not n:
        return False
    for w in words:
        if region:
            l, t, r, b = region
            if not (l <= w.rx <= r and t <= w.ry <= b):
                continue
        if n in _norm(w.text) or _norm(w.text) in n:
            return True
    blob = _norm("".join(w.text for w in words))
    return n in blob


# ---------------------------------------------------------------------------
# Capture + annotate
# ---------------------------------------------------------------------------


def grab_window(hwnd: int, path: str | Path, *, focus: bool = True) -> str:
    from PIL import ImageGrab

    from sapilot.connect.mouse import focus_window

    if focus:
        focus_window(hwnd, settle=0.12)
    import win32gui  # type: ignore

    box = win32gui.GetWindowRect(hwnd)
    img = ImageGrab.grab(bbox=box, all_screens=True)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p)
    return str(p)


def look(hwnd: int, shot_dir: str, name: str = "see") -> ScreenView:
    path = str(Path(shot_dir) / f"{name}.png")
    grab_window(hwnd, path)
    from PIL import Image

    img = Image.open(path)
    words = ocr_words(img)
    status = parse_status_bar(ocr_text(crop_status_bar(img)))
    view = ScreenView(path=path, width=img.size[0], height=img.size[1], words=words, status=status)
    _annotate(view, Path(shot_dir) / f"{name}_som.png")
    return view


def _annotate(view: ScreenView, out: Path) -> None:
    try:
        from PIL import Image, ImageDraw

        img = Image.open(view.path).convert("RGB")
        draw = ImageDraw.Draw(img)
        for i, w in enumerate(view.words[:80]):
            draw.rectangle([w.x, w.y, w.x + w.w, w.y + w.h], outline=(80, 200, 255), width=1)
            draw.text((w.x, max(0, w.y - 10)), f"{i}:{w.text[:16]}", fill=(255, 220, 80))
        img.save(out)
    except Exception as e:
        log.debug("annotate skip: %s", e)


def region_changed(before: str, after: str, box: tuple[int, int, int, int] | None = None) -> float:
    """Mean abs pixel delta in [0, 1] between two shots (optional crop)."""
    from PIL import Image, ImageChops, ImageStat

    a = Image.open(before).convert("L")
    b = Image.open(after).convert("L")
    if a.size != b.size:
        b = b.resize(a.size)
    if box:
        a = a.crop(box)
        b = b.crop(box)
    diff = ImageChops.difference(a, b)
    return float(ImageStat.Stat(diff).mean[0]) / 255.0
