"""figgsite backend — config, paths, env."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = Path(__file__).resolve().parent
DATA = Path(os.environ.get("FIGG_DATA", ROOT / "data"))
DB_PATH = Path(os.environ.get("FIGG_DB", DATA / "figg.db"))
LOCAL_TMP = DATA / "tmp"          # staging before R2 upload
LOCAL_MESH = DATA / "meshes"      # downloaded mesh artifacts before upload
UPLOAD_DIR = Path(os.environ.get("FIGG_UPLOAD_DIR", DATA / "uploads"))  # agent-facing sandbox

# R2: bucket the mesh/photo artifacts live in. rclone remote `r2:` is preconfigured
# on this box, so the remote name and the bucket are separate things:
#   remote name -> rclone remote (where credentials live)
#   bucket      -> path prefix inside that remote
RCLONE_REMOTE = os.environ.get("RCLONE_REMOTE", "r2")
R2_BUCKET = os.environ.get("R2_BUCKET", "figgsite")
RCLONE = os.environ.get("RCLONE", "rclone")
R2_REMOTE = os.environ.get("R2_REMOTE") or f"{RCLONE_REMOTE}:{R2_BUCKET}/"

MESHY_API_KEY = os.environ.get("MESHY_API_KEY", "")
MESHY_BASE = os.environ.get("MESHY_BASE", "https://api.meshy.ai/openapi/v1")

# Upload constraints (from the build prompt: single photo, JPEG/PNG, max 10MB)
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 10 * 1024 * 1024))
ALLOWED_MIME = {"image/jpeg", "image/png"}
MAX_EDGE = 2048                 # downscale anything larger (Meshy is happy, R2 stays cheap)
DAILY_UPLOAD_LIMIT = int(os.environ.get("DAILY_UPLOAD_LIMIT", 3))

# ── free tier ─────────────────────────────────────────────────────────
# The wedge: generation is free, physical is the revenue.
#   mesh   — Meshy credits are the scarce thing, so it's the tightest limit
#   video  — our stack (edge-tts + ffmpeg + 2.5D) costs nothing, so this is
#            only a rate/abuse limit, not a cost limit
FREE_DAILY = {
    "mesh":   int(os.environ.get("FREE_MESH_PER_DAY", "3")),
    "video":  int(os.environ.get("FREE_VIDEO_PER_DAY", "5")),
    "upload": DAILY_UPLOAD_LIMIT,
}
# Free videos carry a watermark; paid does not.
WATERMARK_FREE = os.environ.get("WATERMARK_FREE", "1") == "1"

# Product fan-out — every mesh becomes active in these automatically.
# price in cents. "source" says which fulfilment path renders it.
# "free": covered by the daily allowance (watermarked); paid tiers unlock the
# rest. Generation cost is zero for source="local" (edge-tts + ffmpeg).
PRODUCTS: dict[str, dict] = {
    "figurine":    {"label": "Chibi Figurine",    "price_cents": 1999, "source": "makr3d", "free": False},
    "bauble":      {"label": "Christmas Bauble",  "price_cents": 1299, "source": "retexture", "free": False},
    "video":       {"label": "Talking Video",     "price_cents": 999,  "source": "local",  "free": True},
    "comedy_show": {"label": "Comedy Club Clip",  "price_cents": 0,    "source": "local",  "free": True},
    "card":        {"label": "Greeting Card",     "price_cents": 599,  "source": "prodigi", "free": False},
    "sticker":     {"label": "Sticker Pack",      "price_cents": 499,  "source": "prodigi", "free": False},
    "comedy_set":  {"label": "Custom Comedy Set", "price_cents": 1499, "source": "local",  "free": False},
    "ar_show":     {"label": "AR Comedy Show",    "price_cents": 1499, "source": "ar",     "free": False},
}

# ── Google sign-in ──────────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
PUBLIC_BASE = os.environ.get("PUBLIC_BASE", "https://pog.pet")

# ── agent permissions ───────────────────────────────────────────────
# A user mints a child credential and grants only these. Anything not
# granted is refused — an agent never gets a superset of its parent.
AGENT_PERMISSIONS = {
    "profile:read":   "See the owner's profile, roster and active pog",
    "profile:write":  "Switch which pog is in the spotlight",
    "photos:upload":  "Upload photos",
    "mesh:sculpt":    "Spend free mesh credits",
    "mesh:upload":    "Upload a ready-made GLB (bypasses Meshy)",
    "mesh:read":      "Read mesh status and assets",
    "video:render":   "Render videos (spends video credits)",
    "products:read":  "Read the catalogue and product mockups",
    "products:order": "Place orders (needs Stripe — not yet)",
}
DEFAULT_AGENT_PERMISSIONS = ["profile:read", "mesh:read", "products:read"]

# Scenes a free user can drop their pet into (template id → label).
# comedy_show is the first one we ship, per the plan.
SCENES: dict[str, str] = {
    "comedy_show": "Comedy club",
    "stage":       "Talent-show stage",   # the Perform tab's default
    "wizard":      "Wizard",
    "christmas":   "Christmas",
}

# ── Prodigi catalogue ────────────────────────────────────────────────
# Grounded in docs/prodigi-catalogue.md (prodigi.com/products + Print API v4):
# cards & stationery, stickers, wall art, home & living, games.
# price_cents is EST (cents) — no live Prodigi key on this box, so these are
# placeholders to confirm against the dashboard before anything is listed.
PRODIGI_PRODUCTS: dict[str, dict] = {
    "greeting_card": {"label": "Greeting Card",   "price_cents": 799,  "sku_note": "Fine Art / Classic 5x7",   "shape": "card",   "free": False},
    "postcard":      {"label": "Postcard",        "price_cents": 399,  "sku_note": "A6 postcard",              "shape": "postcard", "free": False},
    "sticker":       {"label": "Sticker Sheet",   "price_cents": 499,  "sku_note": "kiss-cut sheet",           "shape": "sticker", "free": False},
    "framed_print":  {"label": "Framed Print",    "price_cents": 2499, "sku_note": "framed / canvas / metal",  "shape": "print",  "free": False},
    "poster":        {"label": "Poster",          "price_cents": 1299, "sku_note": "wall poster",              "shape": "print",  "free": False},
    "photo_tile":    {"label": "Photo Tile",      "price_cents": 999,  "sku_note": "photo tile",               "shape": "print",  "free": False},
    "cushion":       {"label": "Cushion",         "price_cents": 2999, "sku_note": "home & living",            "shape": "cushion", "free": False},
    "mug":           {"label": "Mug",             "price_cents": 1499, "sku_note": "drinkware",                "shape": "mug",    "free": False},
    "tote":          {"label": "Tote Bag",        "price_cents": 1999, "sku_note": "home & living",            "shape": "tote",   "free": False},
    "notebook":      {"label": "Custom Notebook", "price_cents": 1199, "sku_note": "stationery",                "shape": "notebook", "free": False},
    "jigsaw":        {"label": "Jigsaw Puzzle",   "price_cents": 1899, "sku_note": "multi print area (lid!)",   "shape": "jigsaw", "free": False},
    # Cards & stationery tier per docs/prodigi-tiers.md:36 — grade Q, so the
    # SKU still needs a dashboard lookup before it goes on a real listing.
    # sku present → priced live from Prodigi instead of EST (see backend/prodigi.py)
    "canvas":        {"label": "Stretched Canvas 10\u00d710", "price_cents": 2032,
                      "sku": "GLOBAL-CAN-10X10", "sku_attrs": {"wrap": "White"},
                      "sku_note": "GLOBAL-CAN-10X10 \u00b7 verified live", "shape": "print",
                      "free": False},
    "wrapping_paper": {"label": "Wrapping Paper", "price_cents": 899,
                       "sku_note": "cards & stationery · grade Q — SKU unverified",
                       "shape": "paper", "free": False},
}

API_TOKEN = os.environ.get("API_TOKEN", "")


def ensure_dirs() -> None:
    for p in (DATA, LOCAL_TMP, LOCAL_MESH, UPLOAD_DIR):
        p.mkdir(parents=True, exist_ok=True)


def mint_token() -> str:
    return secrets.token_urlsafe(24)
