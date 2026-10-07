"""Renderer DAG + deterministic cache keys (cardgen.md §9–11).

A revision compiles to jobs; each node's cache key hashes template version +
revision + renderer version + source hashes + output contract + provider
params. Same inputs = same key = free reopen. Headline-only edits re-run
only the final compositor.

Renderers: composite2d is LIVE (PIL, instant); identity_image_v1 and
mesh_scene are STAGED behind provider keys (registered in ai_models.py).
"""
from __future__ import annotations

import hashlib
import json

RENDERER_VERSIONS = {
    "composite2d": 1,
    "identity_image_v1": 0,   # staged: needs image-model provider
    "mesh_scene": 0,          # staged: needs mesh + room binding
    "talking_scene_v1": 0,    # staged: needs lipsync provider
}

DAG = ["copy_validate", "source_select", "preview_compose",
       "identity_render", "identity_qc", "final_compose",
       "web_preview", "print_master",
       "video_script", "video_voice", "video_animate", "video_mux"]


def cache_key(*, template_version: int, revision: int, renderer: str,
              source_hashes: list[str], output_contract: str,
              provider_params: dict | None = None) -> str:
    payload = json.dumps({
        "t": template_version, "r": revision,
        "renderer": renderer, "rv": RENDERER_VERSIONS.get(renderer, 0),
        "src": sorted(source_hashes), "out": output_contract,
        "prov": provider_params or {},
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def plan_jobs(scene: dict, *, only: list[str] | None = None) -> list[str]:
    """Which DAG nodes a revision needs. Headline-only edits skip straight
    to final_compose; identity nodes run only when sources change."""
    if only:
        return [j for j in DAG if j in only]
    return list(DAG)


def fill_slots(template: dict, values: dict) -> tuple[dict, list[str]]:
    """AI fills FIELDS (§5): validate typed slots, never touch geometry."""
    filled, gaps = {}, []
    for sid, slot in (template.get("slots") or {}).items():
        stype = slot.get("type")
        if stype == "subject":
            if not values.get(sid):
                gaps.append(f"slot {sid}: subject required")
            else:
                filled[sid] = values[sid]
        elif stype == "text":
            v = str(values.get(sid, slot.get("default", "")))
            mx = int(slot.get("max_chars") or 0)
            if mx and len(v) > mx:
                gaps.append(f"slot {sid}: {len(v)} chars > max {mx}")
            elif not v and slot.get("required"):
                gaps.append(f"slot {sid}: text required")
            else:
                filled[sid] = v
        else:
            filled[sid] = values.get(sid, slot.get("default"))
    return filled, gaps


def render_pattern(template: dict, filled: dict) -> str:
    """Fill the template's caption_pattern with slot values. Pure string —
    no geometry, no pixels, safe to show before any render."""
    pattern = str(template.get("caption_pattern") or "")
    if not pattern:
        for key in ("headline", "caption", "message", "post", "title"):
            if filled.get(key):
                return str(filled[key])
        return ""
    out = pattern
    for k, v in filled.items():
        out = out.replace("{" + str(k) + "}", str(v))
    return out
