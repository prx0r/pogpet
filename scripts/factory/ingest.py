#!/usr/bin/env python3
"""Factory ingest: classify every archive in data/3dprint, extract mesh files.

    python3 scripts/factory/ingest.py [--redo]

Walks data/3dprint/*.zip (stdlib zipfile only — space-safe, unlike the old
awk one-liner), classifies each member by extension, and extracts real mesh
sources (.stl/.3mf/.step/.stp/.obj) plus licence sheets (.pdf/.txt/.md) to
data/3dprint/_ingest/<slug>/.

Writes data/3dprint/_ingest/manifest.json:
  {slug: {src_zip, kind: model_files|print_files|loose|mixed,
          stl:[...], threemf:[...], step:[...], obj:[...],
          gcode:[...], docs:[...], verdict: editable|convert|needs-model|mixed}}

Verdicts:
  editable  — at least one STL/OBJ (Blender imports today, proven)
  convert   — 3MF/STEP only (normalize_3mf.py or a CAD step can unlock)
  needs-model — gcode only (sliced toolpaths; not editable, fetch model_files)
  mixed     — e.g. STL + STEP (editable now, STEP for later)

data/ is gitignored, so the whole _ingest tree stays out of git.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "data" / "3dprint"
OUT = SRC / "_ingest"

MESH_OK = {".stl", ".obj"}
MESH_CONVERT = {".3mf", ".step", ".stp"}
DOC = {".pdf", ".txt", ".md", ".licence", ".license"}
GCODE = {".gcode", ".bgcode"}


def slug_of(zip_path: Path) -> str:
    s = zip_path.stem
    for suffix in ("-model_files", "_model_files", "-print_files", "_print_files"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return s.strip().lower().replace(" ", "-").replace("(", "").replace(")", "")


def classify(names: list[str]) -> dict:
    found: dict[str, list[str]] = {
        "stl": [], "threemf": [], "step": [], "obj": [],
        "gcode": [], "docs": [], "other": [],
    }
    for n in names:
        if n.endswith("/"):
            continue
        ext = Path(n).suffix.lower()
        base = Path(n).name
        if ext in MESH_OK:
            found["stl" if ext == ".stl" else "obj"].append(n)
        elif ext in MESH_CONVERT:
            if ext == ".3mf":
                found["threemf"].append(n)
            else:
                found["step"].append(n)
        elif ext in DOC or "licen" in base.lower():
            found["docs"].append(n)
        elif ext in GCODE:
            found["gcode"].append(n)
        else:
            found["other"].append(n)
    return found


def kind_of(zip_name: str, found: dict) -> str:
    zl = zip_name.lower()
    if "print_files" in zl or "print-files" in zl:
        return "print_files"
    if "model_files" in zl or "model-files" in zl:
        return "model_files"
    if found["gcode"] and not (found["stl"] or found["threemf"] or found["step"]):
        return "print_files"
    return "mixed"


def verdict_of(found: dict) -> str:
    editable = bool(found["stl"] or found["obj"])
    convert = bool(found["threemf"] or found["step"])
    gcode = bool(found["gcode"])
    if editable and (convert or gcode):
        return "mixed"
    if editable:
        return "editable"
    if convert:
        return "convert"
    if gcode:
        return "needs-model"
    return "unknown"


def ingest(zip_path: Path, redo: bool = False) -> dict:
    slug = slug_of(zip_path)
    dest = OUT / slug
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        found = classify(names)
        kind = kind_of(zip_path.name, found)
        verdict = verdict_of(found)
        if redo or not dest.exists():
            for n in found["stl"] + found["obj"] + found["threemf"] + found["step"] + found["docs"]:
                try:
                    data = z.read(n)
                except KeyError:
                    continue
                target = dest / Path(n).name
                if target.exists() and not redo:
                    continue
                dest.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
    return {
        "src_zip": zip_path.name,
        "kind": kind,
        "verdict": verdict,
        "stl": [Path(n).name for n in found["stl"]],
        "obj": [Path(n).name for n in found["obj"]],
        "threemf": [Path(n).name for n in found["threemf"]],
        "step": [Path(n).name for n in found["step"]],
        "gcode": [Path(n).name for n in found["gcode"]],
        "docs": [Path(n).name for n in found["docs"]],
        "dir": str(dest.relative_to(ROOT)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--redo", action="store_true", help="re-extract even if present")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    zips = sorted(SRC.glob("*.zip"))
    for zp in zips:
        slug = slug_of(zp)
        try:
            entry = ingest(zp, redo=a.redo)
        except zipfile.BadZipFile as e:
            entry = {"src_zip": zp.name, "verdict": "bad-zip", "error": str(e)}
        if slug in manifest and isinstance(manifest[slug], dict):
            # model_files + print_files zips share a slug: merge lists, keep best verdict
            prev = manifest[slug]
            merged = dict(entry)
            for k in ("stl", "obj", "threemf", "step", "gcode", "docs"):
                merged[k] = sorted(set(prev.get(k, []) + entry.get(k, [])))
            merged["src_zip"] = prev.get("src_zip", "") + " + " + entry.get("src_zip", "")
            rank = {"editable": 0, "mixed": 1, "convert": 2, "needs-model": 3, "unknown": 4}
            pv, ev = prev.get("verdict", "unknown"), entry.get("verdict", "unknown")
            if pv == "editable" or ev == "editable":
                merged["verdict"] = "mixed" if (prev.get("gcode") or entry.get("gcode") or prev.get("step") or entry.get("step") or prev.get("threemf") or entry.get("threemf")) else "editable"
            else:
                merged["verdict"] = pv if rank.get(pv, 9) <= rank.get(ev, 9) else ev
            manifest[slug] = merged
        else:
            manifest[slug] = entry
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    by_verdict: dict[str, int] = {}
    for m in manifest.values():
        by_verdict[m.get("verdict", "?")] = by_verdict.get(m.get("verdict", "?"), 0) + 1
    print(f"{len(zips)} zips -> {OUT.relative_to(ROOT)}/manifest.json")
    print("verdicts:", json.dumps(by_verdict))
    need = sorted(s for s, m in manifest.items() if m.get("verdict") in ("convert", "needs-model", "unknown"))
    if need:
        print("needs work:", ", ".join(need))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
