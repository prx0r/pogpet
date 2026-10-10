"""Wrap repeat renderer: motif PNG -> deterministic Prodigi sheet.

Modes: classic (grid), scattered (seeded rotation/offset), badge (motif
in a ring). No generation here — the motif arrives as a finished,
QC-passed asset (transform pipeline). Brown-paper-class edits change the
deterministic layers (background, sprigs), never the motif.
"""
from __future__ import annotations

from PIL import Image as _Image, ImageDraw as _Draw
import hashlib as _hl
import random as _random

# Live Prodigi print areas (print_area, verified 2026-10-10).
SHEET_PX = {
    "WRAP-1-50X70": (2952, 4133),
    "WRAP-1-75X90": (4429, 5314),
    "WRAP-ROL-70X100": (4133, 5905),
}

SPRIG_COLORS = [(183, 28, 28), (27, 94, 32), (255, 255, 255),
                (212, 175, 55)]


def _motif(path: str, cell: int) -> _Image.Image:
    im = _Image.open(path).convert("RGBA")
    im.thumbnail((cell, cell), _Image.LANCZOS)
    return im


def _sprig(d: _Draw.ImageDraw, x: int, y: int, r: int, color: tuple) -> None:
    d.ellipse([x - r, y - r, x + r, y + r], fill=color)


def render_sheet(motif_path: str, *, sku: str = "WRAP-1-50X70",
                 mode: str = "classic", bg: tuple = (18, 56, 45),
                 seed: int = 7) -> _Image.Image:
    """Deterministic sheet at exact print px. Same inputs = same sheet."""
    if sku not in SHEET_PX:
        raise ValueError(f"unknown wrap sku {sku}")
    if mode not in ("classic", "scattered", "badge"):
        raise ValueError(f"unknown mode {mode}")
    W, H = SHEET_PX[sku]
    sheet = _Image.new("RGB", (W, H), bg)
    cell = min(W, H) // 4
    m = _motif(motif_path, cell)
    rnd = _random.Random(seed)
    ring = _Image.new("RGBA", (cell, cell), (0, 0, 0, 0))
    if mode == "badge":
        _Draw.Draw(ring).ellipse([4, 4, cell - 4, cell - 4],
                                 outline=(212, 175, 55, 255), width=max(3, cell // 40))
    rows = H // cell + 1
    cols = W // cell + 1
    for ry in range(rows):
        for cx in range(cols):
            ox = (cell // 2) if (mode != "classic" and ry % 2) else 0
            x = cx * cell + ox - (cell if ox and cx == 0 else 0)
            y = ry * cell
            if mode == "scattered":
                mm = m.rotate(rnd.uniform(-18, 18), expand=True,
                              resample=_Image.BICUBIC)
            else:
                mm = m
            sheet.paste(mm, (x + (cell - mm.width) // 2,
                             y + (cell - mm.height) // 2), mm)
            if mode == "badge":
                sheet.paste(ring, (x, y), ring)
            if (cx * 7 + ry * 13) % 5 == 0:
                _sprig(_Draw.Draw(sheet),
                       (x + rnd.randint(20, cell - 20)) % W,
                       (y + rnd.randint(20, cell - 20)) % H,
                       max(4, cell // 60),
                       SPRIG_COLORS[(cx + ry) % len(SPRIG_COLORS)])
    return sheet


def sheet_preview(sheet: _Image.Image, max_side: int = 900) -> _Image.Image:
    w, h = sheet.size
    s = max_side / max(w, h)
    return sheet.resize((round(w * s), round(h * s)), _Image.LANCZOS)


def sheet_hash(sheet: _Image.Image) -> str:
    return _hl.sha1(sheet.tobytes()).hexdigest()[:16]
