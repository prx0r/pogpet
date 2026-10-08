"""JokeBlock library — reusable hypotheses that some relationship between
ideas is funny.

Ontology (frozen): facts -> connection -> comic model -> theories -> results.
A block stores comic potential (reality AND culture); a premise selects one
interpretation; derivations explore consequences; instantiations express one
consequence in a medium; performance tells us whether the theory was right.

Blocks live in templates/blocks/*.json, theories in templates/theories.json,
voice fingerprints in templates/fingerprints.json.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "templates"
BLOCKS_DIR = ROOT / "blocks"
EVENTS_DIR = ROOT / "events"
THEORIES_PATH = ROOT / "theories.json"
FINGERPRINTS_PATH = ROOT / "fingerprints.json"
FORMATS_PATH = ROOT / "formats.json"

EVENT_STATUSES = ("developing", "resolved", "disputed")
CLAIM_STATUSES = ("confirmed", "reported", "unconfirmed", "disputed")

REQUIRED_BLOCK = ("id", "comic_claim", "reality_model", "comic_model",
                  "theories", "tensions", "characters", "results")
FACT_STATUSES = ("confirmed", "reported", "observed", "comic_model", "unconfirmed")


def _read(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def load_blocks() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not BLOCKS_DIR.is_dir():
        return out
    for f in sorted(BLOCKS_DIR.glob("*.json")):
        b = _read(f)
        if isinstance(b, dict) and b.get("id"):
            out[b["id"]] = b
    return out


def load_theories() -> dict[str, dict]:
    d = _read(THEORIES_PATH) or {}
    return {t["id"]: t for t in d.get("theories", []) if t.get("id")}


def load_fingerprints() -> dict[str, dict]:
    d = _read(FINGERPRINTS_PATH) or {}
    return {m["id"]: m for m in d.get("models", []) if m.get("id")}


def load_formats() -> dict[str, dict]:
    d = _read(FORMATS_PATH) or {}
    return {f["id"]: f for f in d.get("formats", []) if f.get("id")}


def load_cast() -> dict[str, dict]:
    """Public-domain cast registry + unlock schedule. Checkerboard rule:
    only listed allowed_traits may be used; later/protected traits never."""
    d = _read(ROOT / "public_domain_cast.json") or {}
    return {c["id"]: c for c in d.get("characters", []) if c.get("id")}


def validate_cast(c: dict) -> list[str]:
    gaps = []
    for k in ("id", "source_work", "publication_year", "jurisdiction",
              "allowed_traits", "voice"):
        if k not in c:
            gaps.append(f"missing {k}")
    if c.get("voice") != "ORIGINAL ONLY":
        gaps.append("cast voice must be ORIGINAL ONLY (never clone)")
    return gaps


def load_evergreens() -> dict[str, dict]:
    """Trunk id -> trunk. New tree shape {trunks: [...]}; legacy flat
    shape {evergreens: [...]} still loads."""
    d = _read(ROOT / "evergreens.json") or {}
    if "trunks" in d:
        return {t["id"]: t for t in d.get("trunks", []) if t.get("id")}
    return {e["id"]: e for e in d.get("evergreens", []) if e.get("id")}


def narrative_leaves(trunks: dict | None = None) -> dict[str, dict]:
    """Leaf id -> leaf (+ trunk). The persistent map's addressable nodes."""
    out: dict[str, dict] = {}
    for tid, t in (trunks or load_evergreens()).items():
        for leaf in t.get("leaves", []):
            if leaf.get("id"):
                out[leaf["id"]] = {**leaf, "trunk": tid}
    return out


def activate(event_text: str, trunks: dict | None = None) -> list[str]:
    """Current event -> narrative leaf ids it activates (keyword triggers).
    Events merely activate nodes; the persistent map does the remembering."""
    text = (event_text or "").lower()
    hits = []
    for lid, leaf in narrative_leaves(trunks).items():
        if any(k in text for k in leaf.get("triggers", [])):
            hits.append(lid)
    return hits


def load_events() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not EVENTS_DIR.is_dir():
        return out
    for f in sorted(EVENTS_DIR.glob("*.json")):
        e = _read(f)
        if isinstance(e, dict) and e.get("id"):
            out[e["id"]] = e
    return out


def validate_event(e: dict) -> list[str]:
    gaps = []
    for k in ("id", "date", "claims", "status"):
        if k not in e:
            gaps.append(f"missing {k}")
    if e.get("status") not in EVENT_STATUSES:
        gaps.append(f"status must be one of {EVENT_STATUSES}")
    for c in e.get("claims") or []:
        if c.get("status") not in CLAIM_STATUSES:
            gaps.append(f"claim status must be one of {CLAIM_STATUSES}")
    return gaps


def validate_premise(p: dict, blocks: dict | None = None) -> list[str]:
    """Both shapes: seed ({id, text, source_lore}) and canonical
    ({id, statement, operators, oppositions, block})."""
    gaps = []
    if not p.get("id"):
        gaps.append("missing id")
    if not (p.get("statement") or p.get("text")):
        gaps.append("missing statement/text")
    theories = {t["id"] for t in (_read(THEORIES_PATH) or {}).get("theories", [])}
    for t in p.get("operators") or []:
        alias = {"incongruity_resolution": ["incongruity", "resolution"]}.get(t, [t])
        for a in alias:
            if a not in theories:
                gaps.append(f"unknown operator {a}")
    if blocks is not None and p.get("block") and p["block"] not in blocks:
        gaps.append(f"unknown block {p['block']}")
    gtvh = p.get("gtvh") or {}
    if gtvh and not isinstance(gtvh, dict):
        gaps.append("gtvh must be an object")
    for k in ("opposition", "mechanism", "situation", "target",
              "narrative_strategy", "surface"):
        if k in gtvh and not isinstance(gtvh[k], (str, list)):
            gaps.append(f"gtvh.{k} must be text or list")
    return gaps


def validate_block(b: dict) -> list[str]:
    gaps = []
    for k in REQUIRED_BLOCK:
        if k not in b:
            gaps.append(f"missing {k}")
    for th in b.get("theories") or []:
        if not isinstance(th, dict) or "id" not in th:
            gaps.append("theory entries need {id, strength}")
        elif not 0 <= float(th.get("strength", -1)) <= 1:
            gaps.append(f"theory {th.get('id')} strength must be 0..1")
    for f in b.get("facts") or []:
        if f.get("status") not in FACT_STATUSES:
            gaps.append(f"fact status must be one of {FACT_STATUSES}")
    if not isinstance(b.get("results"), list):
        gaps.append("results must be a list")
    theories = {t["id"] for t in (_read(THEORIES_PATH) or {}).get("theories", [])}
    for dv in b.get("derivations") or []:
        if not all(k in dv for k in ("id", "premise", "format", "theories")):
            gaps.append("derivations need {id, premise, format, theories}")
        for t in dv.get("theories") or []:
            if t not in theories:
                gaps.append(f"derivation {dv.get('id')} unknown theory {t}")
        if dv.get("operator") and dv["operator"] not in theories:
            gaps.append(f"derivation {dv.get('id')} unknown operator")
    for c in b.get("connections") or []:
        if c not in _known_block_ids():
            gaps.append(f"unknown connection {c}")
    for r in b.get("references") or []:
        if "url" not in r:
            gaps.append("references need {url, date?, note?}")
    return gaps


def _known_block_ids() -> set[str]:
    return set(load_blocks())


def log_update(block_id: str, change: str, timestamp: str | None = None) -> dict:
    """Append-only history: never mutate facts in place, always append.
    A superseded claim keeps its row with previous_status + reason."""
    import time as _t
    p = BLOCKS_DIR / f"{block_id}.json"
    b = _read(p) or {}
    b.setdefault("changelog", []).append({
        "timestamp": timestamp or _t.strftime("%Y-%m-%d"),
        "change": change, "supersedes": None})
    b.get("identity", {})["last_updated"] = timestamp or _t.strftime("%Y-%m-%d")
    p.write_text(json.dumps(b, indent=2, ensure_ascii=False) + "\n")
    return b


def supersede_claim(block_id: str, claim: str, new_status: str,
                    reason: str, timestamp: str | None = None) -> dict:
    """Retire a claim without deleting it: the fact people believed it is
    itself cultural data."""
    import time as _t
    p = BLOCKS_DIR / f"{block_id}.json"
    b = _read(p) or {}
    found = False
    for section in ("facts",):
        for f in b.get(section) or []:
            if isinstance(f, dict) and f.get("claim") == claim:
                f["previous_status"] = f.get("status")
                f["status"] = new_status
                f["changed_at"] = timestamp or _t.strftime("%Y-%m-%d")
                f["reason"] = reason
                found = True
    for lst in ("reality",):
        r = b.get(lst) or {}
        for key in ("unknown", "false_or_unsupported"):
            if claim in r.get(key, []):
                found = True
        if claim in r.get("confirmed", []):
            found = True
    b = log_update(block_id, f"claim status: {claim} -> {new_status} ({reason})",
                   timestamp)
    if not found:
        raise KeyError(f"claim not found in {block_id}")
    return b


# ── mass-culture gate ────────────────────────────────────────────────
# A story becomes a production JokeBlock only if it clears the audience
# floor: recognizable noun, one-sentence weirdness, live discourse,
# drawable metaphor, multi-operator contradiction, shareable memory.
GATE_CRITERIA = ("recognizable_noun", "one_sentence_weirdness",
                 "live_discourse", "visual_metaphor",
                 "multi_operator", "shared_memory")


def mass_culture_gate(checks: dict) -> dict:
    """checks: {criterion: bool}. Returns pass + score + missing."""
    missing = [c for c in GATE_CRITERIA if not checks.get(c)]
    score = round((len(GATE_CRITERIA) - len(missing)) / len(GATE_CRITERIA), 3)
    return {"pass": not missing, "score": score, "missing": missing}


def premise_index() -> dict[str, dict]:
    """premise_id -> premise across all premises packs. Handles both the
    seed shape ({id, text, source_lore}) and the canonical shape
    ({id, statement, operators, oppositions, block})."""
    out: dict[str, dict] = {}
    for pack in sorted((ROOT / "premises").glob("*.json")):
        d = _read(pack)
        for p in (d or {}).get("premises", []):
            if p.get("id"):
                out[p["id"]] = p
    return out


def children(blocks: dict[str, dict], parent_id: str) -> list[dict]:
    return [b for b in blocks.values() if b.get("parent") == parent_id]


def lineage(blocks: dict[str, dict], block_id: str) -> list[dict]:
    """Block + ancestors, root first."""
    chain, cur = [], blocks.get(block_id)
    while cur:
        chain.append(cur)
        cur = blocks.get(cur.get("parent") or "")
    return chain[::-1]
