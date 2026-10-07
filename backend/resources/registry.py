"""External resources — reference clones kept beside the registries.

Normalized records for third-party code we learn from (never vendor).
Clones live in backend/resources/repos/ (gitignored, shallow, re-clone
anytime). Sits next to backend/suppliers.py (plastic) and
backend/ai_models.py (intelligence): three registries, one pattern.
"""
from __future__ import annotations

from pathlib import Path

REPOS_DIR = Path(__file__).resolve().parent / "repos"

RESOURCES: dict[str, dict] = {
    "spark": {
        "label": "Spark — 3D Gaussian Splatting renderer for THREE.js",
        "repo": "https://github.com/storytold/spark",
        "upstream": "https://github.com/sparkjsdev/spark (World Labs)",
        "license": "MIT",
        "local": "backend/resources/repos/spark",
        "relevance": "splat rooms without Marble: render comedy-club backdrops "
                     "in-browser from Gaussian splats (npm @sparkjsdev/spark)",
        "use_for": ["perform venue backdrops", "greeting rooms", "video scenes"],
        "status": "cloned — evaluate against Marble room queue",
    },
    "printcraft": {
        "label": "PrintCraft — PDF workbench (clean-room Acrobat, Rust)",
        "repo": "https://github.com/storytold/printcraft",
        "license": "MIT OR Apache-2.0",
        "local": "backend/resources/repos/printcraft",
        "relevance": "print-ready card PDFs with real bleed handling for "
                     "trade printers (Mixam/Prodigi); Rust workspace, agent docs in-repo",
        "use_for": ["card print.pdf path", "bleed/spine enforcement", "pack zips"],
        "status": "cloned — compare with current exporters",
    },
    "designcraft": {
        "label": "DesignCraft — page layout/publishing (clean-room InDesign, Rust)",
        "repo": "https://github.com/storytold/designcraft",
        "license": "MIT OR Apache-2.0",
        "local": "backend/resources/repos/designcraft",
        "relevance": "multi-panel card layout engine (front/inside/back, fold, spine) "
                     "matching our paper design contracts; runs native + WASM",
        "use_for": ["card template layout", "folded formats", "paper contracts"],
        "status": "cloned — map template model to CARD_DESIGN_CONTRACTS",
    },
    "photocraft": {
        "label": "PhotoCraft — image layers (clean-room Photoshop, Rust)",
        "repo": "https://github.com/storytold/photocraft",
        "license": "MIT OR Apache-2.0",
        "local": "backend/resources/repos/photocraft",
        "relevance": "agent-drivable (UI/CLI/JSON/MCP, WASM) image layers for the "
                     "free deterministic render backend",
        "use_for": ["scene plates", "cutout finishing", "card compositing"],
        "status": "cloned — prototype free render backend",
    },
    "filmcraft": {
        "label": "FilmCraft — video assembly (clean-room Premiere, Rust)",
        "repo": "https://github.com/storytold/filmcraft",
        "license": "MIT OR Apache-2.0",
        "local": "backend/resources/repos/filmcraft",
        "relevance": "timeline/colour/effects/export via commands, JSON and MCP — "
                     "final video assembly for the free path",
        "use_for": ["clip assembly", "lower thirds", "final MP4"],
        "status": "cloned — prototype free render backend",
    },
    "effectcraft": {
        "label": "EffectCraft — motion graphics (After Effects-like, Rust)",
        "repo": "https://github.com/storytold/effectcraft",
        "license": "MIT OR Apache-2.0",
        "local": "backend/resources/repos/effectcraft",
        "relevance": "layers/keyframes/306 effects/text/3D cameras/Lottie + MCP — "
                     "animated card scenes and video overlays",
        "use_for": ["animated scenes", "motion graphics", "video overlays"],
        "status": "cloned — prototype free render backend",
    },
    "noslop": {
        "label": "NoSlop — AI slop detection + diagnosis (prx0r)",
        "repo": "https://github.com/prx0r/noslop",
        "license": "unlicensed upstream — reference import only, never vendored",
        "local": "backend/resources/repos/noslop",
        "relevance": "v6 pattern engine (NARR/NEG/3LIST/CLICHE/FLAT) + repair "
                     "guidance as the no-slop filter on every generated script",
        "use_for": ["script QC filter", "rewrite guidance", "slop budgets"],
        "status": "cloned — comedy-calibrated wrapper in backend/funny/",
    },
}


def get(resource_id: str) -> dict:
    """One resource record, plus whether its clone is present on disk."""
    rec = dict(RESOURCES.get(resource_id, {}))
    if rec:
        rec["cloned"] = (REPOS_DIR / resource_id).is_dir()
    return rec


def listed() -> list[str]:
    """Every resource id we track."""
    return sorted(RESOURCES.keys())
