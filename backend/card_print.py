"""Prodigi single-file compositor — one RGB PDF per order.

The renderer owns vendor geometry: fold, bleed, safe zones, panel order,
final pixels. The AI never sees coordinates. Panel order below must be
confirmed against Prodigi's official greeting-card template before the
first LIVE order; dims are enforced from the cached live spec regardless.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from backend import config
from backend import prodigi as _prodigi
from backend.card_scenes import front, inside

# left-to-right panel order in the flat file. CONFIRM against the official
# template before the first live order (dims are enforced either way).
PANEL_ORDER = ("back", "front", "inside_left", "inside_right")


def compose(design: dict, assets: dict,
            dest: Path | str | None = None) -> Path:
    """Render front + inside + back into the SKU's exact print-area pixels."""
    spec = _prodigi.print_area("CLASSIC-GRE-FEDR-7X5-BLA")
    W, H = spec["horizontalResolution"], spec["verticalResolution"]
    pw = W // 4
    f = front(design, assets, pw, H).convert("RGB")
    inner = inside(design, pw * 2, H).convert("RGB")
    from backend.card_scenes import back as back_panel
    back = back_panel(design, pw, H).convert("RGB")
    panels = {"back": back, "front": f,
              "inside_left": inner.crop((0, 0, pw, H)),
              "inside_right": inner.crop((pw, 0, pw * 2, H))}
    sheet = Image.new("RGB", (W, H), "#ffffff")
    for i, name in enumerate(PANEL_ORDER):
        sheet.paste(panels[name], (i * pw, 0))
    if W % 4:
        sheet.paste(Image.new("RGB", (W - pw * 4, H), "#ffffff"), (pw * 4, 0))
    dest = Path(dest) if dest else \
        config.DATA / "cards" / "cache" / "prodigi-single.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, "PDF", resolution=300)
    return dest


def preflight(path: Path | str) -> list[str]:
    """Reject anything that doesn't match the cached live spec exactly.
    Reads PDF page geometry (PIL can't parse PDF); 300dpi => px/300 inches."""
    spec = _prodigi.print_area("CLASSIC-GRE-FEDR-7X5-BLA")
    gaps = []
    p = Path(path)
    if not p.is_file():
        return ["print file missing"]
    if p.suffix.lower() != ".pdf":
        return ["Prodigi card input must be PDF"]
    try:
        from pypdf import PdfReader
        box = PdfReader(str(p)).pages[0].mediabox
        wpt, hpt = float(box.width), float(box.height)
    except Exception:
        return ["print file unreadable"]
    want_w = spec["horizontalResolution"] / 300 * 72
    want_h = spec["verticalResolution"] / 300 * 72
    if abs(wpt - want_w) > 2 or abs(hpt - want_h) > 2:
        gaps.append(f"print is {wpt:.0f}x{hpt:.0f}pt, SKU wants "
                    f"{want_w:.0f}x{want_h:.0f}pt")
    return gaps
