"""Template authoring pipeline (§16): validate → fixtures → publish.

Author in templates/<style>/<id>/manifest.json, run publish() to validate
against the schema, render every fixture through fill+QC, and only then bump
the version in place. A template goes live when all fixtures pass.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import jobs, templates
from .artifacts import qc_card_copy

FIXTURES = [
    {"star": "sub_dad", "headline": "DAD", "caption": "short"},
    {"star": "sub_mum", "headline": "MUM SPECIAL", "caption": "x" * 90},
    {"star": "sub_pet", "headline": "GOOD BOY"},
    {"star": "sub_x", "headline": "A NAME THAT IS EXACTLY FORTY TWO CHARS!!",
     "caption": "y" * 200},
]


def gate(template: dict) -> tuple[bool, list[str]]:
    """Would this template go live? Every fixture must fill + QC-pass,
    and over-long fields must fail."""
    problems = []
    slots = template.get("slots", {})
    for i, f in enumerate(FIXTURES):
        known = {k: v for k, v in f.items() if k in slots or k == "star"}
        known["star"] = f["star"]
        filled, gaps = jobs.fill_slots(template, known)
        gaps += qc_card_copy(filled, template)
        over = any(k in slots and isinstance(slots[k], dict)
                   and slots[k].get("type") == "text"
                   and isinstance(slots[k].get("max_chars"), int)
                   and len(str(f.get(k, ""))) > slots[k]["max_chars"] for k in f)
        if over and not gaps:
            problems.append(f"fixture {i}: over-long field passed")
        elif not over and gaps:
            problems.append(f"fixture {i}: {gaps}")
    return (not problems), problems


def publish(style: str, template_id: str, root: Path | None = None) -> dict:
    """Validate + gate, then bump version in place. Returns the published manifest."""
    from .templates import ROOT as DEFAULT
    base = Path(root) if root else DEFAULT
    path = base / style / template_id / "manifest.json"
    m = json.loads(path.read_text())
    gaps = templates.validate_manifest(m)
    if gaps:
        return {"ok": False, "gaps": gaps}
    live, problems = gate(m)
    if not live:
        return {"ok": False, "gaps": problems}
    m["version"] = int(m.get("version", 0)) + 1
    path.write_text(json.dumps(m, indent=2) + "\n")
    return {"ok": True, "id": template_id, "version": m["version"]}
