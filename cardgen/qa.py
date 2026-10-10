"""Step 5: QA gates on generated front art. Each gate returns (ok, detail).

First proof run (Chris, couple poster): v1 came back with a stray "A TECHNICOLOR"
tagline that OCR could not read (stylised), and the vision critic caught it. v2 had a
tiny gibberish credits line, and the OCR gate caught it ("MOGNORE", "POAR"). An edit_fix
removed it, and v3 passed both. So: OCR is a cheap pre-filter, the vision critic is the gate.
"""
from __future__ import annotations
import re, subprocess


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^A-Z0-9 ]", " ", s.upper()).split())


def ocr_words(path: str, min_conf: int = 85) -> list[str]:
    """High-confidence words only: painted textures make low-confidence junk."""
    out = subprocess.run(["tesseract", path, "-", "--psm", "11", "tsv"], capture_output=True, text=True).stdout
    words = []
    for line in out.splitlines()[1:]:
        c = line.split("\t")
        if len(c) == 12 and c[11].strip() and float(c[10]) >= min_conf:
            words += _norm(c[11]).split()
    return words


def text_gate(path: str, expected: list[str]) -> tuple[bool, str]:
    """No confident 4+ letter word outside the copy. Missing words are reported but
    don't fail (stylised lettering defeats OCR); the vision critic confirms spelling."""
    got = ocr_words(path)
    want = set(_norm(" ".join(expected)).split())
    extra = [w for w in got if len(w) >= 4 and w.isalpha() and w not in want]
    missing = sorted(w for w in want if len(w) >= 3 and w not in got)
    return not extra, f"extra={extra} missing={missing}"


def faces_gate(photo, expected: int | None, hero_vecs: list[list], min_sim: float = 0.30) -> tuple[bool, str]:
    """photo: a cardgen.photos.Photo indexed from the generated art."""
    n = len(photo.faces)
    if expected is not None and n != expected:
        return False, f"faces={n} expected={expected}"
    if hero_vecs:
        cos = lambda a, b: sum(x * y for x, y in zip(a, b))
        best = max((cos(f.vec, v) for f in photo.faces if f.vec for v in hero_vecs), default=0)
        if best < min_sim:
            return False, f"likeness={best:.2f} < {min_sim}"
        return True, f"faces={n} likeness={best:.2f}"
    return True, f"faces={n}"


FIX_PROMPTS = {
    "extra_text": "Edit this exact image: remove every piece of lettering except {keep}. Fill removed areas with the surrounding background. Keep everything else identical.",
    "likeness": "Edit this exact image: make {who}'s face match the reference photos exactly (same face shape, eyes, smile, hair). Keep the style, pose and everything else identical.",
}
