"""Named normalisation recipes.

A recipe is the exact set of Cloudflare Images options we send, plus the QC
thresholds the output has to clear. Keeping them as data (not code) means a
new use case is a new entry, not a new code path — the greeting-card subject
cut and the Meshy pre-mesh normalise are the same function with different
options.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class QCConfig:
    """What the transformed output must satisfy to be accepted."""

    min_side: int = 512          # short side
    min_long: int = 0            # long side (0 = don't care)
    max_side: int = 4096
    require_alpha: bool = True
    # Fraction of the frame the cut-out subject must cover. Too small means
    # segmentation isolated the wrong thing (or nothing); too large means the
    # subject still touches the frame edges, i.e. background survived.
    min_coverage: float = 0.02
    max_coverage: float = 0.99
    aspect_min: float = 0.15
    aspect_max: float = 6.0


@dataclass(frozen=True)
class Recipe:
    name: str
    blurb: str
    options: tuple[str, ...]
    qc: QCConfig = field(default_factory=QCConfig)
    # Optional first pass, applied to the *source* before the main options —
    # used for AI upscaling, which must never run after `segment` because the
    # upscale path drops the alpha channel it produced.
    prelude: tuple[str, ...] = ()
    # Run `prelude` only when the source's short side is below this.
    prelude_below: int = 0


# Option order matters: Cloudflare applies them in a fixed pipeline order
# (segment → trim → fit/resize → sharpen → format), so we list them in the
# order the docs describe the pipeline, not the order we think about them.
RECIPES: dict[str, Recipe] = {
    # Pre-mesh input for the Creative Lab figure / image-to-3D: subject alone,
    # on a square transparent canvas, long side at least 1024. Small inputs
    # get an AI-upscale *prelude* — after `segment` the upscale path drops the
    # alpha channel, so it has to run on the source, before the cut-out.
    "meshy": Recipe(
        name="meshy",
        blurb="Subject cut out, centred, >=1024 long side, for Meshy photo-to-3D",
        options=(
            "segment=foreground",
            "trim=border",
            "fit=contain",
            "w=1024",
            "h=1024",
            "sharpen=1",
            "metadata=none",
            "format=png",
        ),
        qc=QCConfig(min_side=512, min_long=1024, max_side=2048, min_coverage=0.03),
        prelude=("fit=contain", "w=1400", "h=1400",
                 "upscale=generate", "metadata=none", "format=png"),
        prelude_below=700,
    ),
    # Greeting-card / sticker source: subject on transparency, larger canvas,
    # no square constraint — the card layout crops and composes downstream.
    "card": Recipe(
        name="card",
        blurb="Subject cut out at high resolution, transparent, uncropped",
        options=(
            "segment=foreground",
            "trim=border",
            "fit=scale-down",
            "w=1600",
            "h=1600",
            "sharpen=1",
            "metadata=none",
            "format=png",
        ),
        qc=QCConfig(min_side=400, max_side=1600, min_coverage=0.03),
        prelude=("fit=contain", "w=1600", "h=1600",
                 "upscale=generate", "metadata=none", "format=png"),
        prelude_below=900,
    ),
    # Passthrough: make the file MEET THE SPEC and touch nothing else.
    # Creative Lab figure wants a normal photo (the webapp never sends a
    # cutout) — segmenting it there made the stylizer invent props.
    # Empty options == no Cloudflare call at all: QC the bytes, return them.
    "photo": Recipe(
        name="photo",
        blurb="Validate only: original bytes, no segmentation, no crop, no resize",
        options=(),
        qc=QCConfig(min_side=400, max_side=4096, require_alpha=False,
                    min_coverage=0.0, max_coverage=1.0,
                    aspect_min=0.1, aspect_max=8.0),
    ),
    # Cheap derived thumbnail — no segmentation, so no alpha required.
    # NOTE: this zone currently ignores `format=` (segmented output is always
    # PNG, everything else echoes the source format), so we ask for JPEG
    # quality and read the real container back from the bytes.
    "thumb": Recipe(
        name="thumb",
        blurb="Plain <=512px thumbnail for lists and previews",
        options=(
            "fit=scale-down",
            "w=512",
            "h=512",
            "sharpen=1",
            "metadata=none",
            "q=82",
        ),
        qc=QCConfig(min_side=200, max_side=512, require_alpha=False,
                    min_coverage=0.0, max_coverage=1.0),
    ),
}


def get(name: str) -> Recipe:
    try:
        return RECIPES[name]
    except KeyError:
        raise KeyError(
            f"unknown recipe {name!r} — have: {', '.join(sorted(RECIPES))}"
        ) from None
