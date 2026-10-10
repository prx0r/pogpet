"""Slot primitive: fixed mesh + typed slots (no remesh, no Meshy).

Source of truth: backend/slot_specs/dart_stand.json (imported from the
product team). Fields name/tagline/arc with fonts/caps/zones, colour
palettes with contrast rule, JLC process. Validator hard-errors (never
silent-truncate) so agents retry with nicknames. Autofill pulls slots
from the family profile (nickname → display first word → initials; arc
from relation; tagline from interests; base = nearest palette swatch by
CIELAB ΔE; accent = highest contrast, gold preferred on dark).
Preview: slot compositor over blank plates when present (scripts/
slot_compose.py); PIL fallback otherwise. Print mesh at checkout only
(manifold, staged).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SPEC_DIR = Path(__file__).resolve().parent / "slot_specs"


def load_spec(line: str = "dart_stand") -> dict:
    p = SPEC_DIR / f"{line}.json"
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text())
    except ValueError:
        return {}


def clean(field: dict, value: str | None) -> str:
    """Port of dart_gen.clean: defaults, upper, charset, length. Raises."""
    s = (field.get("default", "") if value is None else value).upper().strip()
    s = re.sub(r"\s+", " ", s)
    bad = set(s) - set(field.get("charset", ""))
    if bad:
        raise ValueError(f"unsupported characters {sorted(bad)}")
    if not (field.get("min_len", 0) <= len(s) <= field.get("max_len", 99)):
        raise ValueError(f"length {len(s)} not in "
                         f"{field.get('min_len')}-{field.get('max_len')}")
    return s


def validate(line: str, slots: dict) -> dict:
    """Validate + resolve slots. Returns {ok, resolved} or raises ValueError.
    resolved: {name, tagline, arc, base, accent} with cap widths checked."""
    spec = load_spec(line)
    if not spec:
        raise ValueError(f"no slot spec for {line}")
    F = spec.get("fields", {})
    resolved = {}
    for key in ("name", "tagline", "arc"):
        if key not in F:
            continue
        val = (slots or {}).get(key)
        if val is None and key != "name":
            resolved[key] = ""
            continue
        resolved[key] = clean(F[key], val)
    cols = _resolve_colours(spec, (slots or {}).get("colours") or {})
    resolved.update(cols)
    return {"ok": True, "resolved": resolved}


def _hex(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lab(rgb: tuple) -> tuple:
    """sRGB → CIELAB (D65). Compact, no deps."""
    def inv(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (inv(c) for c in rgb)
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = (r * 0.2126 + g * 0.7152 + b * 0.0722) / 1.0
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _de(a: tuple, b: tuple) -> float:
    la, lb = _lab(a), _lab(b)
    return sum((x - y) ** 2 for x, y in zip(la, lb)) ** 0.5


def nearest_swatch(target_hex: str, palette: dict) -> str:
    """Nearest palette swatch by ΔE. Unknown target → '' (no opinion)."""
    try:
        t = _hex(target_hex)
    except (ValueError, IndexError):
        return ""
    best, best_d = "", 1e9
    for name, hx in palette.items():
        try:
            d = _de(t, _hex(hx))
        except (ValueError, IndexError):
            continue
        if d < best_d:
            best, best_d = name, d
    return best


def contrast_ok(base_hex: str, accent_hex: str, minimum: float = 30.0) -> bool:
    try:
        return _de(_hex(base_hex), _hex(accent_hex)) > minimum
    except (ValueError, IndexError):
        return False


def _resolve_colours(spec: dict, want: dict) -> dict:
    cols = spec.get("colours", {})
    base_pal = (cols.get("base") or {}).get("palette", {})
    acc_pal = (cols.get("accent") or {}).get("palette", {})
    base = str(want.get("base") or (cols.get("base") or {}).get("default", ""))
    if base not in base_pal:
        base = (cols.get("base") or {}).get("default", "")
    accent = str(want.get("accent") or "")
    if accent not in acc_pal:
        accent = _best_accent(base_pal.get(base, "#232427"), acc_pal)
    return {"base": base, "accent": accent}


def _best_accent(base_hex: str, palette: dict) -> str:
    """Highest-contrast swatch vs base, gold preferred on dark bases."""
    try:
        base_l = _lab(_hex(base_hex))[0]
    except (ValueError, IndexError):
        base_l = 50.0
    scored = []
    for name, hx in palette.items():
        try:
            d = _de(_hex(base_hex), _hex(hx))
        except (ValueError, IndexError):
            continue
        bonus = 5.0 if (name == "gold" and base_l < 50) else 0.0
        scored.append((d + bonus, name))
    scored.sort(reverse=True)
    if not scored:
        return ""
    return scored[0][1]


def autofill(owner: str, subject_id: str, buyer_relation: str = "") -> dict:
    """Slots from the family profile. Name: nickname → display first word →
    initials (never silent-truncate — caller validates and errors back).
    Arc: dad→DAD'S DARTS, grandad→GRANDAD'S OCHE, else NAME'S DARTS.
    Tagline: darts interest → 180 CLUB. Base: favourite_colour ΔE nearest.
    Accent: contrast rule."""
    from backend import subjects as _subjects
    from backend import db as _db
    slots: dict[str, str] = {}
    with _db.connect() as c:
        sub = _subjects.get_subject(c, owner, subject_id)
        if not sub:
            return {"ok": False, "error": "friend not found"}
        prof = _subjects.profile_for(c, owner, subject_id)
    p = prof.get("profile", {}) or {}
    name = (p.get("nickname") or sub.get("name") or "").strip()
    if not name:
        return {"ok": False, "error": "subject has no name to fill"}
    first = name.split()[0]
    slots["name"] = first
    slots["_name_fallbacks"] = [n for n in
                                [p.get("nickname"), first,
                                 "".join(w[0] for w in name.split() if w)]
                                if n]
    rel = (buyer_relation or prof.get("relationship", "")).strip().lower()
    if rel in ("dad", "father"):
        slots["arc"] = "DAD'S DARTS"
    elif rel in ("grandad", "grandfather"):
        slots["arc"] = "GRANDAD'S OCHE"
    else:
        slots["arc"] = f"{first.upper()}'S DARTS"
    interests = [str(i).lower() for i in (p.get("interests") or [])]
    if any("dart" in i for i in interests):
        slots["tagline"] = "180 CLUB"
    fav = (p.get("favourite_colour") or "").strip()
    if fav:
        spec = load_spec()
        pal = ((spec.get("colours") or {}).get("base") or {}).get("palette", {})
        hit = nearest_swatch(fav, pal)
        if hit:
            slots.setdefault("colours", {})["base"] = hit
    return {"ok": True, "slots": slots}
