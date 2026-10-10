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

# Marble rooms are infrastructure (one generation, infinite sets), so the key
# follows the same rules as Meshy: env only, ask-first, ledgered. Empty = the
# rooms system runs on local backdrops for $0 (see ROOMS below).
MARBLE_API_KEY = os.environ.get("MARBLE_API_KEY", "")

# ── conversational voice brain ───────────────────────────────────────
# Server-side only. The provider/model are env-swappable so the latest best
# voice model slots in with no code change. Empty key = stub sessions.
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GEMINI_VOICE_PROVIDER = os.environ.get("GEMINI_VOICE_PROVIDER", "")
GEMINI_VOICE_MODEL = os.environ.get(
    "GEMINI_VOICE_MODEL", "gemini-live-2.5-flash-native-audio")

# ── greeting rooms ───────────────────────────────────────────────────
# One backdrop PNG per venue, generated once, reused forever. Files live
# gitignored under data/rooms/; a missing file falls back to the white void,
# never an error. Portrait 1080x1920, empty (no people, no text).
ROOMS: dict[str, dict] = {
    "void":  {"label": "White void", "blurb": "Clean control background.", "backdrop": ""},
    "club":  {"label": "Comedy club", "blurb": "Brick wall, spotlight, mic. Roasts live here.",
              "backdrop": "data/rooms/club.png"},
    "podium": {"label": "Podium", "blurb": "Curtain, flags, grave announcements. Parody-safe.",
               "backdrop": "data/rooms/podium.png"},
    "press": {"label": "Press room", "blurb": "Sponsor wall. Transfer news and victory speeches.",
              "backdrop": "data/rooms/press.png"},
    "xmas":  {"label": "Christmas living room", "blurb": "Fire, tree, armchair. Eve messages.",
              "backdrop": "data/rooms/xmas.png"},
}

# Upload constraints (from the build prompt: single photo, JPEG/PNG, max 10MB)
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 10 * 1024 * 1024))
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_EDGE = 2048                 # downscale anything larger (Meshy is happy, R2 stays cheap)
DAILY_UPLOAD_LIMIT = int(os.environ.get("DAILY_UPLOAD_LIMIT", 30))

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
# Watermark brand string — follows the storefront brand, never hardcoded.
# (video.py composes frames outside a request context, so it reads this.)
WATERMARK_BRAND = os.environ.get("WATERMARK_BRAND", "")  # empty -> derived below

# ── owner signatures (anti-spoof) ────────────────────────────────────
# Browser visitors used to be able to POST owner=<anyone> and burn that
# owner's free sculpt/video credits (audit H1). Writes now need either a
# real user API key or an owner_sig minted by POST /api/session for the
# exact owner string. The secret derives from API_TOKEN so it is stable
# across restarts without new env; override with OWNER_SIGNING_SECRET.
OWNER_SIGNING_SECRET = os.environ.get("OWNER_SIGNING_SECRET", "")


def owner_secret() -> str:
    if OWNER_SIGNING_SECRET:
        return OWNER_SIGNING_SECRET
    if API_TOKEN:
        return "owner-sig:" + API_TOKEN
    # last resort: persist a stable secret locally so every process agrees.
    # (A random-per-call secret would make sign/verify never match.)
    try:
        p = DATA / ".owner_secret"
        if p.is_file() and len(p.read_text().strip()) >= 16:
            return p.read_text().strip()[:64]
        import secrets as _secrets
        s = _secrets.token_hex(32)
        DATA.mkdir(parents=True, exist_ok=True)
        p.write_text(s)
        try:
            p.chmod(0o600)
        except OSError:
            pass
        return s
    except OSError:
        return "owner-sig:ephemeral"


def sign_owner(owner: str) -> str:
    """HMAC-SHA256(owner, secret) truncated — the proof you own this owner id."""
    import hashlib
    import hmac
    o = (owner or "").strip()[:80]
    if not o:
        return ""
    return hmac.new(owner_secret().encode(), o.encode(), hashlib.sha256).hexdigest()[:32]


def verify_owner(owner: str, sig: str) -> bool:
    import hmac
    expect = sign_owner(owner)
    return bool(expect) and bool(sig) and hmac.compare_digest(expect, str(sig)[:64])


def watermark_brand() -> str:
    """Brand string burned into free-tier video frames."""
    if WATERMARK_BRAND:
        return WATERMARK_BRAND
    return BRANDS[DEFAULT_BRAND_HOST]["brand"]


def watermark_domain() -> str:
    if WATERMARK_BRAND:
        b = BRANDS.get(WATERMARK_BRAND) or {}
        return b.get("domain", DEFAULT_BRAND_HOST)
    return BRANDS[DEFAULT_BRAND_HOST].get("domain", DEFAULT_BRAND_HOST)

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

# ── studio: modular product lines + prop library ─────────────────────
# Studio tab = character select + loadout config (NO prices).
# Products tab = storefront for the same lines (prices + order + MCP).
# CONTROLLED custom only: fixed prop IDs + retexture params. No free-form mesh.
STUDIO_LINES: dict[str, dict] = {
    "ornament": {
        "label": "Xmas ornament",
        "product": "bauble",
        "scale_mm": 80,
        "hardware": "printed loop",
        "blurb": "Tree hanger. Loop is part of the print.",
        "status": "live",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 1500,
        "assets": {
            "hats": ["none", "santa", "xmas_hat"],
            "coats": ["none", "cream", "golden", "chocolate", "black", "fawn", "grey"],
            "patterns": ["solid", "spots", "stripes", "fairisle"],
        },
        "theme": "xmas",
        "fulfilment": "print_farm",
        "personalization": {"method": "face_swap", "zone": "full_mesh", "max_chars": 0},
    },
    "keychain": {
        "label": "Keychain / keyring",
        "product": "figurine",
        "scale_mm": 60,
        "hardware": "printed loop + ring",
        "blurb": "Same design, smaller. No metal.",
        "status": "live",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 1500,
        "assets": {
            "hats": ["none"],
            "coats": ["none", "cream", "golden", "chocolate", "black", "fawn", "grey"],
            "patterns": ["solid", "spots", "stripes"],
        },
        "theme": "everyday",
        "fulfilment": "print_farm",
        "personalization": {"method": "face_swap", "zone": "full_mesh", "max_chars": 0},
    },
    "croc_tag": {
        "label": "Croc tag pin",
        "product": "figurine",
        "scale_mm": 28,
        "hardware": "printed pin stem (Jibbitz-style)",
        "blurb": "Charm that pops into Croc holes. Same mesh, tiny print.",
        "status": "live",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 1000,
        "assets": {
            "hats": ["none"],
            "coats": ["none"],
            "patterns": ["solid"],
        },
        "theme": "everyday",
        "fulfilment": "print_farm",
        "personalization": {"method": "face_swap", "zone": "full_mesh", "max_chars": 0},
        "size_mm": 28,
        "pin_diameter_mm": 12,
        "fits": "Crocs classic / most jibbitz holes",
    },
    "gift_card": {
        "label": "Gift card",
        "product": "gift_card",
        "scale_mm": 0,
        "hardware": "none",
        "blurb": "Digital credit. Redeem on any OddHobb product.",
        "status": "live",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 2000,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "gift",
        "fulfilment": "digital",
        "amounts_cents": [500, 1000, 1500, 2000],
    },
    "brick": {
        "label": "Brick figure",
        "product": "figurine",
        "scale_mm": 75,
        "hardware": "none",
        "blurb": "Desk figure — your star as a 75 mm brick-style minifig. Two figures live.",
        "status": "live",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 2000,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "desk",
        "fulfilment": "print_farm",
        "personalization": {"method": "face_swap", "zone": "full_mesh", "max_chars": 0},
    },
    # ── Christmas 20 factory lines (canonical format v1 — see factory_registry.json).
    # status "soon": visible in shop with fallback stills, not orderable until
    # stills render + MAKR3D sample lands, then flip to "live".
    "clog_charm": {
        "label": "Personalised Clog Shoe Charm",
        "product": "figurine",
        "scale_mm": 16,
        "hardware": "printed pin stem (Jibbitz-style)",
        "blurb": "Name/pet/face/hobby on a Jibbitz-style post. Tiny, instant gift.",
        "status": "soon",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 500,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "stocking",
        "fulfilment": "print_farm",
        "material": "PETG", "colors_max": 4,
        "dims_mm": [16.3, 12.0, 15.1], "weight_g": 1.6,
        "weight_basis": "measured heart-croc-jibbitz at 100% (upper bound)",
        "fits": "Crocs classic / most clog holes",
        "personalization": {"method": "relief", "zone": "top_face", "max_chars": 10},
        "supplier": "makr3d",
        "recipes": {"render": "todo", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
    "bag_charm": {
        "label": "Personalised Bag Charm",
        "product": "figurine",
        "scale_mm": 16,
        "hardware": "printed loop + split-ring seat",
        "blurb": "Pet/person/motif charm for bags and zips.",
        "status": "soon",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 1000,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "stocking",
        "fulfilment": "print_farm",
        "material": "PLA", "colors_max": 4,
        "dims_mm": [16.3, 12.0, 15.1], "weight_g": 1.6,
        "weight_basis": "measured heart-croc-jibbitz at 100% (upper bound)",
        "fits": "bags, zips, keyrings",
        "personalization": {"method": "relief", "zone": "front_face", "max_chars": 10},
        "supplier": "makr3d",
        "recipes": {"render": "todo", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
    "brick_keychain": {
        "label": "Custom Brick/Person Keychain",
        "product": "figurine",
        "scale_mm": 60,
        "hardware": "printed loop + printed ring",
        "blurb": "Brick-style minifig keychain from your photo. No metal.",
        "status": "live",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 1000,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "stocking",
        "fulfilment": "print_farm",
        "material": "PLA", "colors_max": 4,
        "dims_mm": [60, 40, 20], "weight_g": None,
        "weight_basis": "brick mesh at 60mm (measure at master time)",
        "fits": "keys, bags",
        "personalization": {"method": "face_swap", "zone": "full_mesh", "max_chars": 0},
        "supplier": "makr3d",
        "recipes": {"render": "live", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "have",
    },
    "keycap": {
        "label": "Personalised Cherry-MX Artisan Keycap",
        "product": "figurine",
        "scale_mm": 18,
        "hardware": "none (female MX cruciform socket)",
        "blurb": "Female MX socket, blank canvas top. Gamer stocking filler.",
        "status": "live",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 1500,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "gamer",
        "fulfilment": "print_farm",
        "material": "PLA", "colors_max": 4,
        "dims_mm": [18.0, 18.0, 12.0], "weight_g": 2.9,
        "weight_basis": "measured masters/mx_keycap.stl at 100% (upper bound)",
        "fits": "Cherry-MX stems",
        "personalization": {"method": "relief", "zone": "cap_top", "max_chars": 6},
        "supplier": "makr3d",
        "recipes": {"render": "live", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
    "shoelace_charm": {
        "label": "Personalised Shoelace Charm Pair",
        "product": "figurine",
        "scale_mm": 30,
        "hardware": "lace-loop interface",
        "blurb": "Clog-charm engine reused for trainers. Pet/name/initial/hobby.",
        "status": "soon",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 1000,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "stocking",
        "fulfilment": "print_farm",
        "material": "PETG", "colors_max": 4,
        "dims_mm": [30.0, 17.0, 3.0], "weight_g": 1.6,
        "weight_basis": "measured shoe-lace-tag.stl at 100% (upper bound)",
        "fits": "standard trainer laces",
        "personalization": {"method": "relief", "zone": "top_face", "max_chars": 8},
        "supplier": "makr3d",
        "recipes": {"render": "todo", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
    "book_holder": {
        "label": "Personalised Book Thumb Page Holder",
        "product": "figurine",
        "scale_mm": 63,
        "hardware": "none",
        "blurb": "26mm thumb ring + paddle. ~3g print, BookTok audience.",
        "status": "live",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 500,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "stocking",
        "fulfilment": "print_farm",
        "material": "PLA", "colors_max": 4,
        "dims_mm": [63.0, 32.0, 6.0], "weight_g": 3.3,
        "weight_basis": "measured masters/book_holder.stl at 100% (upper bound)",
        "fits": "thumb ID 26mm",
        "personalization": {"method": "emboss", "zone": "paddle_face", "max_chars": 12},
        "supplier": "makr3d",
        "recipes": {"render": "live", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
    "golf_marker": {
        "label": "Personalised Golf Ball Marker",
        "product": "figurine",
        "scale_mm": 24,
        "hardware": "none (flat marker)",
        "blurb": "Names, initials, pets, jokes, club motif. Evergreen gift.",
        "status": "live",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 1000,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "stocking",
        "fulfilment": "print_farm",
        "material": "PLA", "colors_max": 4,
        "dims_mm": [24.0, 12.0, 24.0], "weight_g": 1.2,
        "weight_basis": "measured marker-template at 100% (upper bound)",
        "fits": "hat-clip / pocket",
        "personalization": {"method": "relief", "zone": "top_face", "max_chars": 10},
        "supplier": "makr3d",
        "recipes": {"render": "live", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
    "straw_charm": {
        "label": "Personalised Tumbler Straw Charm",
        "product": "figurine",
        "scale_mm": 34,
        "hardware": "none",
        "blurb": "ID ring + topper pad. Charm format, no food-contact claims.",
        "status": "live",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 300,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "stocking",
        "fulfilment": "print_farm",
        "material": "PETG", "colors_max": 4,
        "dims_mm": [34.0, 24.0, 4.0], "weight_g": 1.6,
        "weight_basis": "measured masters/straw_ring.stl at 100% (upper bound)",
        "fits": "~10mm straws (ring ID 10.5)",
        "personalization": {"method": "relief", "zone": "topper_pad", "max_chars": 8},
        "supplier": "makr3d",
        "recipes": {"render": "live", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
    "controller_stand": {
        "label": "Personalised Controller Stand",
        "product": "figurine",
        "scale_mm": 125,
        "hardware": "none",
        "blurb": "Gamertag embossed. Broad gamer gift, obvious on a desk.",
        "status": "soon",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 2000,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "gamer",
        "fulfilment": "print_farm",
        "material": "PLA", "colors_max": 4,
        "dims_mm": [124.5, 67.6, 56.9], "weight_g": 286.9,
        "weight_basis": "ref stand.stl at 100% — COST RISK, slim or re-quote before listing",
        "fits": "Xbox/PS5 pads (per variant)",
        "personalization": {"method": "emboss", "zone": "fascia", "max_chars": 14},
        "supplier": "makr3d",
        "recipes": {"render": "todo", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
    "train_station": {
        "label": "Mexican Train Family Station",
        "product": "figurine",
        "scale_mm": 111,
        "hardware": "none",
        "blurb": "Family name + functional hub. Niche gift differentiator.",
        "status": "soon",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 2000,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "game_night",
        "fulfilment": "print_farm",
        "material": "PLA", "colors_max": 4,
        "dims_mm": [111.2, 59.0, 5.5], "weight_g": 16.3,
        "weight_basis": "measured Train Hub Half at 100% (upper bound)",
        "fits": "double-9/12 dominoes (verify tile size)",
        "personalization": {"method": "emboss", "zone": "hub_face", "max_chars": 18},
        "supplier": "makr3d",
        "recipes": {"render": "todo", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
    "domino_racks": {
        "label": "Personalised Mexican Train Domino Racks",
        "product": "figurine",
        "scale_mm": 150,
        "hardware": "none",
        "blurb": "MUM / DAD / TOM / SARAH. Family set, upsell to the station.",
        "status": "soon",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 2000,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "game_night",
        "fulfilment": "print_farm",
        "material": "PLA", "colors_max": 4,
        "dims_mm": [200.0, 40.0, 25.0], "weight_g": 274.9,
        "weight_basis": "measured masters/domino_rack.stl at 100%",
        "fits": "double-9/12 dominoes (verify tile size)",
        "personalization": {"method": "emboss", "zone": "rack_fascia", "max_chars": 10},
        "supplier": "makr3d",
        "recipes": {"render": "todo", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
    "line_reader": {
        "label": "Personalised Mahjong Line Reader",
        "product": "figurine",
        "scale_mm": 180,
        "hardware": "none",
        "blurb": "Exploding category, tiny print, huge name surface.",
        "status": "live",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 1000,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "game_night",
        "fulfilment": "print_farm",
        "material": "PLA", "colors_max": 4,
        "dims_mm": [180.0, 46.0, 4.0], "weight_g": 17.5,
        "weight_basis": "measured masters/line_reader.stl at 100% (upper bound)",
        "fits": "standard mahjong tiles (verify channel)",
        "personalization": {"method": "emboss", "zone": "plate_face", "max_chars": 12},
        "supplier": "makr3d",
        "recipes": {"render": "live", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
    "wind_indicator": {
        "label": "Personalised Mahjong Wind Indicator",
        "product": "figurine",
        "scale_mm": 80,
        "hardware": "snap-fit wheel (2 parts)",
        "blurb": "Tiny quirky add-on. Geometry still to author.",
        "status": "soon",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 1500,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "game_night",
        "fulfilment": "print_farm",
        "material": "PLA", "colors_max": 4,
        "dims_mm": None, "weight_g": None,
        "weight_basis": "author at master time (~13g target)",
        "fits": "tabletop",
        "personalization": {"method": "emboss", "zone": "base_ring", "max_chars": 8},
        "supplier": "makr3d",
        "recipes": {"render": "todo", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
    "rummy_rack": {
        "label": "Personalised 4-Tier Rummy Tile Rack",
        "product": "figurine",
        "scale_mm": 200,
        "hardware": "none",
        "blurb": "Simple stepped geometry, big name fascia. Family packs later.",
        "status": "soon",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 1500,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "game_night",
        "fulfilment": "print_farm",
        "material": "PLA", "colors_max": 4,
        "dims_mm": [200.0, 58.0, 40.0], "weight_g": 134.9,
        "weight_basis": "measured masters/rummy_rack.stl at 100% — check infill cost",
        "fits": "rummy tiles (verify tile size)",
        "personalization": {"method": "emboss", "zone": "back_fascia", "max_chars": 12},
        "supplier": "makr3d",
        "recipes": {"render": "todo", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
    "card_rack": {
        "label": "Personalised Playing-Card Hand Rack",
        "product": "figurine",
        "scale_mm": 180,
        "hardware": "none",
        "blurb": "180mm 3-groove hand rack. Canasta, Bridge, Hand & Foot.",
        "status": "live",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 1500,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "game_night",
        "fulfilment": "print_farm",
        "material": "PLA", "colors_max": 4,
        "dims_mm": [180.0, 50.0, 8.0], "weight_g": 67.6,
        "weight_basis": "own card_hand_rack master at 100% — confirm infill cost",
        "fits": "poker 63.5x88.9 / bridge 57x88.8 (verify groove)",
        "personalization": {"method": "emboss", "zone": "front_fascia", "max_chars": 12},
        "supplier": "makr3d",
        "recipes": {"render": "live", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
    "tcg_stand": {
        "label": 'Personalised TCG "Grail" Stand',
        "product": "figurine",
        "scale_mm": 110,
        "hardware": "none",
        "blurb": "110mm easel for PSA/toploader slabs. No character IP needed.",
        "status": "live",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 1500,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "gamer",
        "fulfilment": "print_farm",
        "material": "PLA", "colors_max": 4,
        "dims_mm": [110.0, 53.2, 70.7], "weight_g": 74.2,
        "weight_basis": "own slab_stand master at 100% (upper bound)",
        "fits": "PSA/toploader slabs (9mm groove, <=7mm + sleeve)",
        "personalization": {"method": "emboss", "zone": "base_front", "max_chars": 14},
        "supplier": "makr3d",
        "recipes": {"render": "live", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
    "cribbage_pegs": {
        "label": "Personalised Cribbage Peg Pair",
        "product": "figurine",
        "scale_mm": 32,
        "hardware": "none",
        "blurb": "Own peg master, 3.0-3.2mm shaft for 1/8in holes. Sculptural topper.",
        "status": "soon",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 1500,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "stocking",
        "fulfilment": "print_farm",
        "material": "PETG", "colors_max": 4,
        "dims_mm": [31.7, 4.7, 4.7], "weight_g": 0.5,
        "weight_basis": "measured Cribbage_peg_5.stl at 100% (upper bound)",
        "fits": "1/8in cribbage holes (shaft ~3.0-3.2mm)",
        "personalization": {"method": "relief", "zone": "topper", "max_chars": 0},
        "supplier": "makr3d",
        "recipes": {"render": "todo", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
    "dart_stand": {
        "label": "Personalised Dart Stand",
        "product": "figurine",
        "scale_mm": 40,
        "hardware": "none",
        "blurb": "DAD'S DARTS, 180 CLUB. Obvious family gift, one-shot print.",
        "status": "soon",
        "production": "sample_pending",  # split 2026-10-08: catalog status above stays; Etsy-live needs verified
        "etsy": "draft",
        "price_cents": 2000,
        "assets": {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]},
        "theme": "game_night",
        "fulfilment": "print_farm",
        "material": "PLA", "colors_max": 4,
        "dims_mm": [25.0, 40.0, 33.3], "weight_g": 7.5,
        "weight_basis": "measured dart_stand.stl at 100% (upper bound)",
        "fits": "standard brass/tungsten darts (verify bore)",
        "personalization": {"method": "emboss", "zone": "base_front", "max_chars": 14},
        "supplier": "makr3d",
        "recipes": {"render": "todo", "production_3mf": "todo"},
        "occasion": "christmas", "sample": "needed",
    },
}

# ── Manufacturing: exact process + supplier per line ──────────────────
# JLC is a production partner, not turnkey fulfilment (docs/jlc-manufacturing.md).
# Additive routing only: lines absent here keep existing fulfilment behaviour.
# Grimoirer/Ochema/Glimlings folded under OddHobb until a category earns identity.
JLC_PROCESS: dict[str, str] = {
    "brick": "WJP Tough multicolour (quote standard WJP alongside)",
}
PRIMARY_SUPPLIER: dict[str, str] = {
    "brick": "jlc",
}
# Lines absent here -> existing supplier fields (makr3d/print farm, paper, metal).
# Customers never pick raw materials; lines resolve to a profile.
# ABS + Nylon profiles exist but stay unassigned until a product needs them.
# ── JLC manufacturing constraints (docs/jlc-design-guide.md) ──────────
# Numbers are JLC-published starting points, not guarantees. Design with
# margin above minimums. jlc_check() gates a geometry.mesh_report() dict.
JLC_CONSTRAINTS: dict[str, dict] = {
    "FDM": {"min_wall_mm": 1.2, "clearance_mm": 0.5, "tol_mm": 0.3},
    "SLA": {"min_wall_mm": 0.8, "clearance_mm": 0.5, "tol_mm": 0.2},
    "SLS_MJF": {"min_wall_mm": 1.0, "clearance_mm": 0.6, "tol_mm": 0.3},
    "SLM": {"min_wall_mm": 1.5, "clearance_mm": 1.0, "tol_mm": 0.3},
    "BJ": {"min_wall_mm": 1.5, "clearance_mm": 1.0, "tol_mm": 0.3},
    "WJP": {"min_wall_mm": 1.0, "clearance_mm": 1.5, "tol_mm": 0.2,
            "emboss_mm": 0.8, "max_mm": [380, 330, 230]},
    "WJP_TOUGH": {"min_wall_mm": 0.8, "clearance_mm": 1.5, "tol_mm": 0.2,
                  "emboss_mm": 0.8, "max_mm": [390, 340, 240]},
    "BJ_METAL": {"min_wall_mm": 1.5, "clearance_mm": 1.0, "tol_mm": 0.3,
                 "detail_mm": 1.0, "shrink_pct": [10, 15]},
    "SLM_METAL": {"min_wall_mm": 1.5, "clearance_mm": 1.0, "tol_mm": 0.3,
                  "detail_mm": 1.0},
    "CNC": {"detail_mm": 0.1, "uv_dpi": 1440, "laser_depth_mm": [0.03, 0.1]},
}


def jlc_check(report: dict, process: str) -> list[str]:
    """Verdicts for a geometry.mesh_report() dict against a JLC process.
    min_dim is a documented proxy for wall readiness, not a wall measurement.
    Empty list = pass."""
    c = JLC_CONSTRAINTS.get(process)
    if c is None:
        return [f"unknown process {process}"]
    out = []
    if report.get("manifold_issues"):
        out.append(f"manifold: {report['manifold_issues']} issues (must be 0)")
    dims = report.get("dims_mm") or [0, 0, 0]
    if any(d > m for d, m in zip(dims, c.get("max_mm", [10**9] * 3))):
        out.append(f"exceeds {process} build volume {dims}mm")
    thin = min((d for d in dims if d > 0), default=0)
    if thin < c["min_wall_mm"]:
        out.append(f"thinnest extent below {process} wall minimum {c['min_wall_mm']}mm (proxy — verify thin features)")
    if process in ("BJ_METAL", "SLM_METAL", "CNC"):
        out.append("note: small glyphs go to laser marking, not geometry (1mm detail floor)")
    return out


def laser_text_ok(text: str, face_mm: float) -> list[str]:
    """Text legibility gate: 0.4mm min coloured line, 0.5mm min laser char."""
    per = face_mm / max(1, len(text))
    if per < 0.5:
        return [f"text too small for laser ({per:.2f}mm/char < 0.5mm) — shorten or enlarge face"]
    return []



PRINTIE_PROFILES: dict[str, dict] = {
    "display": {"material": "PLA", "use": "figures, ornaments, collectables, decorative game pieces"},
    "durable": {"material": "PETG", "use": "racks, keychains, storage, functional accessories"},
    "flexible": {"material": "TPU", "use": "grips, bumpers, sleeves, flexible attachments"},
    "outdoor": {"material": "ASA", "use": "garden accessories, weather-exposed parts"},
    "heat": {"material": "ABS", "use": "specialised heat-exposed indoor housings", "enabled": False},
    "mechanical": {"material": "Nylon", "use": "hinges, snap-fits, load-bearing mechanisms", "enabled": False},
}
# Studio line -> profile. Lines absent here resolve to "display".
# ── Catalog tiers: flagships earn identity, fillers earn volume ──────
# Stonedoorway Stone enters as concept (docs/stonedoorway-thesis.md).
PRODUCT_TIERS: dict[str, str] = {
    "brick": "flagship",
    "ornament": "flagship",
    "stone": "flagship",
    "keychain": "filler",
    "croc_tag": "filler",
    "brick_keychain": "filler",
    "clog_charm": "filler",
    "bag_charm": "filler",
}
STUDIO_LINES["stone"] = {
    "label": "Stonedoorway Stone V1 (concept)",
    "product": "device",
    "status": "concept",
    "production": "sample_pending",
    "etsy": "draft",
    "price_cents": 0,
    "theme": "flagship",
    "fulfilment": "bench_prototype",
    "material": "translucent resin shell + BLE core",
    "personalization": {"method": "none", "zone": "firmware_identity", "max_chars": 0},
}


LINE_PRINTIE_PROFILE: dict[str, str] = {
    "keychain": "durable",
    "croc_tag": "durable",
    "brick_keychain": "durable",
    "clog_charm": "durable",
    "bag_charm": "flexible",
}


# ── design contracts (the design space for models) ────────────────────
# Per line: what is LOCKED (functional interfaces a designer must not move),
# the working envelope, material, and rough cost targets at makr3d + printie
# (ex-VAT estimates — live quotes win). Anything marked "verify" needs its
# MAKR3D sample before the number is trusted. A model designing for a line
# must keep every locked interface and stay inside the envelope; everything
# else is free.
DESIGN_CONTRACTS: dict[str, dict] = {
    "ornament": {
        "origin": "mesh",
        "locked": ["printed loop: hole dia 5.0mm, wire 2.4mm", "hang axis through CoM column"],
        "envelope_mm": [90, 90, 100], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 28.0, "cost_target_cents": {"makr3d": 250, "printie": 390},
        "verify": [],
    },
    "keychain": {
        "origin": "mesh",
        "locked": ["printed loop + ring: ring hole dia 4.0mm", "no metal anywhere"],
        "envelope_mm": [70, 70, 90], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 14.0, "cost_target_cents": {"makr3d": 170, "printie": 200},
        "verify": [],
    },
    "croc_tag": {
        "origin": "mesh",
        "locked": ["pin stem dia 4.2mm (fits ~5mm Croc holes)", "stopper disc dia >= 6mm",
                   "face dia <= 32mm so it clears neighbouring holes"],
        "envelope_mm": [32, 32, 18], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 2.5, "cost_target_cents": {"makr3d": 100, "printie": 100},
        "verify": ["pin fit on a real Croc hole"],
    },
    "gift_card": {
        "origin": "digital",
        "locked": [], "envelope_mm": [0, 0, 0], "material": "digital", "colors_max": 0,
        "volume_cm3_est": 0.0, "cost_target_cents": {"makr3d": 0, "printie": 0},
        "verify": [],
    },
    "brick": {
        "origin": "mesh",
        "locked": ["minifig scale: overall 75mm", "footprint fits 6x6 stud grid (48mm pitch 8.0mm)"],
        "envelope_mm": [60, 60, 80], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 22.0, "cost_target_cents": {"makr3d": 250, "printie": 310},
        "verify": [],
    },
    "clog_charm": {
        "origin": "reference",
        "locked": ["pin stem dia 5.0mm (Jibbitz post)", "retention head dia >= 12mm",
                   "face <= 30mm"],
        "envelope_mm": [30, 30, 18], "material": "PETG", "colors_max": 4,
        "volume_cm3_est": 1.6, "cost_target_cents": {"makr3d": 100, "printie": 100},
        "verify": ["pin fit on a real Croc hole"],
    },
    "bag_charm": {
        "origin": "reference",
        "locked": ["split-ring seat hole dia >= 5.0mm", "strap slot width 8mm if present"],
        "envelope_mm": [40, 40, 20], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 3.0, "cost_target_cents": {"makr3d": 100, "printie": 100},
        "verify": [],
    },
    "brick_keychain": {
        "origin": "mesh",
        "locked": ["printed loop + ring: ring hole dia 4.0mm", "minifig scale 60mm", "no metal"],
        "envelope_mm": [50, 50, 70], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 12.0, "cost_target_cents": {"makr3d": 150, "printie": 170},
        "verify": [],
    },
    "keycap": {
        "origin": "reference",
        "locked": ["Cherry MX stem: cross 4.0x4.0mm outer, wall 1.2mm, mount depth 4.5mm",
                   "cap top zone 12x12mm for relief"],
        "envelope_mm": [18, 18, 14], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 1.8, "cost_target_cents": {"makr3d": 100, "printie": 100},
        "verify": ["stem fit on a real MX switch"],
    },
    "shoelace_charm": {
        "origin": "reference",
        "locked": ["lace channel 8x3mm clear", "wall >= 1.6mm around channel"],
        "envelope_mm": [30, 20, 12], "material": "PETG", "colors_max": 4,
        "volume_cm3_est": 1.5, "cost_target_cents": {"makr3d": 100, "printie": 100},
        "verify": ["channel fit on a real lace"],
    },
    "book_holder": {
        "origin": "reference",
        "locked": ["thumb pad >= 18mm wide", "page slot 2.5mm (holds ~40 pages)"],
        "envelope_mm": [60, 40, 25], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 6.0, "cost_target_cents": {"makr3d": 100, "printie": 100},
        "verify": [],
    },
    "golf_marker": {
        "origin": "reference",
        "locked": ["dia 24mm (measured marker-template)", "thickness 2.0mm", "flat top ±0.2mm"],
        "envelope_mm": [24, 24, 4], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 1.2, "cost_target_cents": {"makr3d": 100, "printie": 100},
        "verify": [],
    },
    "straw_charm": {
        "origin": "reference",
        "locked": ["ring inner dia 7.0mm (grips 6mm straws)", "wall >= 1.6mm"],
        "envelope_mm": [30, 30, 16], "material": "PETG", "colors_max": 4,
        "volume_cm3_est": 1.5, "cost_target_cents": {"makr3d": 100, "printie": 100},
        "verify": ["ring grip on a real straw"],
    },
    "controller_stand": {
        "origin": "reference",
        "locked": ["cradle width >= 165mm (standard pad)", "support arms reach 60mm deep",
                   "base footprint stable at 200x140mm"],
        "envelope_mm": [220, 160, 140], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 90.0, "cost_target_cents": {"makr3d": 1080, "printie": 1260},
        "verify": ["fit on a real controller", "weight/cost — 287g flagged"],
    },
    "train_station": {
        "origin": "reference",
        "locked": ["8 hub slots, each >= 50x26mm face for double-12 dominoes",
                   "slot depth >= 13mm"],
        "envelope_mm": [160, 160, 40], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 40.0, "cost_target_cents": {"makr3d": 480, "printie": 560},
        "verify": ["slot fit on real double-12 dominoes"],
    },
    "domino_racks": {
        "origin": "reference",
        "locked": ["rack groove width >= 25mm, depth >= 13mm (double-12)",
                   "4-player set geometry"],
        "envelope_mm": [220, 60, 40], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 25.0, "cost_target_cents": {"makr3d": 300, "printie": 350},
        "verify": ["groove fit on real dominoes"],
    },
    "line_reader": {
        "origin": "reference",
        "locked": ["tile channel inner width >= 23mm, height >= 15mm (slides over a mahjong face)"],
        "envelope_mm": [120, 40, 25], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 8.0, "cost_target_cents": {"makr3d": 100, "printie": 115},
        "verify": ["channel fit on real mahjong tiles"],
    },
    "wind_indicator": {
        "origin": "reference",
        "locked": ["base ring seats a rotating wheel: axle dia 6mm, wheel dia <= 60mm",
                   "numbers legible at 8mm cap height"],
        "envelope_mm": [80, 80, 25], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 10.0, "cost_target_cents": {"makr3d": 120, "printie": 140},
        "verify": ["geometry not yet authored — wheel + base to be designed"],
    },
    "rummy_rack": {
        "origin": "reference",
        "locked": ["4-tier grooves: pitch 6mm, depth >= 5mm, tile lean 70deg",
                   "holds 40+ tiles per rack"],
        "envelope_mm": [260, 60, 60], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 30.0, "cost_target_cents": {"makr3d": 360, "printie": 420},
        "verify": ["groove fit on real rummy tiles"],
    },
    "card_rack": {
        "origin": "reference",
        "locked": ["grooves 2.5mm wide (sleeved cards)", "rack length >= 200mm for a full hand"],
        "envelope_mm": [220, 60, 50], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 20.0, "cost_target_cents": {"makr3d": 240, "printie": 280},
        "verify": [],
    },
    "tcg_stand": {
        "origin": "reference",
        "locked": ["slab cradle inner >= 56mm wide, 90mm tall (PSA slab 85x54x7)",
                   "lean angle 75deg"],
        "envelope_mm": [100, 80, 120], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 15.0, "cost_target_cents": {"makr3d": 180, "printie": 210},
        "verify": ["cradle fit on a real slab"],
    },
    "cribbage_pegs": {
        "origin": "reference",
        "locked": ["shaft dia 3.0–3.2mm (sliding fit for 1/8in=3.175mm holes)",
                   "all parts manifold, print-ready"],
        "envelope_mm": [12, 12, 40], "material": "PETG", "colors_max": 4,
        "volume_cm3_est": 1.0, "cost_target_cents": {"makr3d": 100, "printie": 100},
        "verify": [],
    },
    "dart_stand": {
        "origin": "reference",
        "locked": ["3 bores dia 12mm, depth 40mm (barrel + flight clearance)",
                   "base stable at 120x80mm"],
        "envelope_mm": [130, 90, 60], "material": "PLA", "colors_max": 4,
        "volume_cm3_est": 35.0, "cost_target_cents": {"makr3d": 420, "printie": 490},
        "verify": ["bore fit on real darts"],
    },
}

for _lid, _contract in DESIGN_CONTRACTS.items():
    if _lid in STUDIO_LINES:
        STUDIO_LINES[_lid]["design_contract"] = _contract
del _lid, _contract

# ── personalisation levels (agent-visible contract) ─────────────────
# L0 name/initials (instant, no Meshy) · L1 photo/2D asset (seconds) ·
# L2 relief/silhouette (short) · L3 full 3D mesh (slowest, costs credits).
# Derived per line from personalization.method — no per-line bookkeeping:
#   emboss    -> L0, requires recipient_name, modes [text]
#   relief    -> L0+L2, requires nothing, modes [text, relief]
#   face_swap -> L3, requires photo, modes [full_mesh]
# Overrides only where a line spans further (golf marker takes a pet face).
CUSTOM_SCHEMA_OVERRIDES = {
    "golf_marker": {
        "requires": [],
        "optional": ["recipient_name", "initials", "motif", "colour", "photo"],
        "modes": ["text", "relief", "pet_mesh"],
        "levels": ["L0", "L2"],
    },
}

# Greeting cards are a structured 2D composition problem, not manufacturing:
# requires occasion; everything else optional. Agents compose semantically.
CARD_CUSTOMIZATION_SCHEMA = {
    "requires": ["occasion"],
    "optional": ["recipient", "photo", "message", "style", "inside_message"],
    "modes": ["photo", "illustrated", "character", "typography"],
    "levels": ["L1", "L2", "L3"],
}

# ── friends: interest → motif picks ─────────────────────────────────
# The engine personalises by profile, not just face: golf-Dad's clog charm
# is a golf ball, not a portrait. First interest with motifs wins; lines
# take the suggestion through suggested_motif (advisory, checkout omits it
# until the customer confirms — the profile proposes, the human disposes).
INTEREST_MOTIFS = {
    "golf": ["golf_ball", "tee", "flag", "club"],
    "darts": ["dartboard", "dart", "180"],
    "football": ["ball", "boot", "scarf"],
    "liverpool": ["liver_bird", "red_star", "ynwa"],
    "fishing": ["fish", "hook", "fly"],
    "reading": ["book", "glasses", "bookmark"],
    "gaming": ["controller", "keycap", "d20"],
    "cycling": ["bike", "wheel", "helmet"],
    "gardening": ["flower", "leaf", "trowel"],
    "music": ["note", "guitar", "vinyl"],
    "dogs": ["paw", "bone", "face"],
    "cats": ["paw", "fish", "face"],
    "mahjong": ["tile", "wind", "flower"],
    "christmas": ["tree", "star", "bauble"],
}

# Coat = material grade + optional pattern on the existing texture (previews).
# Production multi-colour is a live farm quote — never pretend a grade is a print SKU.
STUDIO_COATS: list[dict] = [
    {"id": "none",     "label": "As printed", "hex": ""},
    {"id": "cream",    "label": "Cream",      "hex": "#EADBBE"},
    {"id": "golden",   "label": "Golden",     "hex": "#E6B86B"},
    {"id": "chocolate","label": "Chocolate",  "hex": "#6B4229"},
    {"id": "black",    "label": "Black",      "hex": "#1F1F1F"},
    {"id": "fawn",     "label": "Fawn",       "hex": "#D1AD85"},
    {"id": "grey",     "label": "Grey",       "hex": "#8C8C8F"},
]

# Controlled retexture patterns (Blender shader presets — not free-form art).
STUDIO_PATTERNS: list[dict] = [
    {"id": "solid",    "label": "Solid",     "blurb": "Flat colour on the coat"},
    {"id": "spots",    "label": "Spots",     "blurb": "Irregular dots (dalmatian-ish)"},
    {"id": "stripes",  "label": "Stripes",   "blurb": "Horizontal bands"},
    {"id": "fairisle", "label": "Fair Isle", "blurb": "Knit-style geometric"},
]

# Hats = free Blender props seated on the measured skull. Controlled IDs only.
# Assets: OGA CC0 + Khodrin (edit+redistribute) under data/assets/hats/.
STUDIO_HATS: list[dict] = [
    {"id": "none",     "label": "None",       "asset": "", "status": "live"},
    {"id": "santa",    "label": "Santa hat",  "asset": "data/assets/hats/oga-santa/santa_hat.fbx",
     "status": "live", "licence": "CC0", "source": "OpenGameArt", "lines": ["ornament"]},
    {"id": "xmas_hat", "label": "Xmas hat",   "asset": "data/assets/hats/khodrin-christmas/christmas_hat.fbx",
     "status": "live", "licence": "edit+redistribute", "source": "Khodrin",
     "lines": ["ornament"], "maps": ["Albedo.png", "Normal.png"]},
]

# Canonical product GLB (loop amend) served from /img/prod/ — demo + fallback
STUDIO_CANONICAL_GLB = "/img/prod/chibi-figure-hook.glb"
STUDIO_JAW_GLB = "/img/prod/chibi-figure-hook-jaw.glb"
# Nibble proof: first personalised jibbit (mini mesh + pin, watertight)
STUDIO_NIBBLE_JIBBIT_GLB = "/img/prod/nibble-jibbit.glb"
STUDIO_NIBBLE_JIBBIT_PORTRAIT = "/img/prod/nibble-jibbit-hero.png"
# Brick desk figures — parent GLBs from Creative Lab / svatantrya imports
STUDIO_BRICK_GLB = "/img/prod/brick-figure.glb"
STUDIO_BRICK_PORTRAIT = "/img/prod/brick-hero.png"
# Second brick variant (svatantrya 01a0ff52) — studio lineup shows both
STUDIO_BRICK2_GLB = "/img/prod/brick-figure-2.glb"
STUDIO_BRICK2_PORTRAIT = "/img/prod/brick-hero-2.png"
STUDIO_BRICKS = [
    {
        "id": "brick-demo",
        "label": "brick figure",
        "glb_url": STUDIO_BRICK_GLB,
        "portrait": STUDIO_BRICK_PORTRAIT,
        "style_id": "brick-figure",
        "source": "svatantrya:01a0feb8",
        "mesh_ids": ["msh_a984c413e47f48a19b63"],
    },
    {
        "id": "brick-demo-2",
        "label": "brick figure 2",
        "glb_url": STUDIO_BRICK2_GLB,
        "portrait": STUDIO_BRICK2_PORTRAIT,
        "style_id": "brick-figure-2",
        "source": "svatantrya:01a0ff52",
        "mesh_ids": ["msh_8802c242b583455b9159"],
    },
]
# mesh_id → studio label/portrait for installed brick pogs
STUDIO_BRICK_MESH_MAP = {
    "msh_a984c413e47f48a19b63": ("brick figure", STUDIO_BRICK_PORTRAIT, "brick-demo"),
    "msh_8802c242b583455b9159": ("brick figure 2", STUDIO_BRICK2_PORTRAIT, "brick-demo-2"),
}
STUDIO_STILL_DIR = "prod"  # data/productimg/prod → /img/prod/
# Calling-card portrait under the character select (exact product still)
STUDIO_CALLING_CARD = "/img/prod/prod-hero.png"

# Controlled custom is what MCP exposes. Free-form mesh edits stay out.
STUDIO_CUSTOM_POLICY = {
    "mode": "controlled",
    "allowed": ["coat_color", "coat_pattern", "hat_id", "line", "qty", "amount_cents"],
    "blocked": ["arbitrary_mesh", "unlisted_hat", "unlisted_pattern", "text_decal_until_live"],
    "note": "Agents pick from registries only. Full free custom is not enabled.",
}

# ── Personal cards (Xmas etc.) — Cards tab + Etsy listings ───────────
# Mix: dog mesh still + greeting text; or a real uploaded PNG.
# Sizes locked to print-farm common SKUs (see PRODIGI + oddhobbies ETSY-SETUP).
CARD_SIZES: dict[str, dict] = {
    "A6":    {"label": "A6 postcard",   "mm": "105 × 148", "price_cents": 399,
              "note": "Standard postcard · fits mail slots"},
    "5x7":   {"label": "5×7 card",      "mm": "127 × 178", "price_cents": 799,
              "note": "Fine Art greeting card · envelope included"},
    "A5":    {"label": "A5 card",       "mm": "148 × 210", "price_cents": 999,
              "note": "Larger greeting card"},
    "A4":    {"label": "A4 print",      "mm": "210 × 297", "price_cents": 1499,
              "note": "Wall print / poster"},
}

PERSONAL_CARDS: dict[str, dict] = {
    "merry_xmas": {
        "label": "Merry Xmas card",
        "message": "Merry Xmas",
        "sub": "from the whole pack",
        "source": "mesh",          # mesh still + text
        "theme": "christmas",
        "price_cents": 799,
        "sizes": ["A6", "5x7", "A5"],
        "tags": ["christmas card", "personalised pet", "xmas gift", "dog card", "custom card"],
        "blurb": "Your pet's 3D render on a Christmas card. Upload once — print on cards, ornaments, keychains.",
        "etsy_title": "Personalised Pet Christmas Card | Custom Dog Card | Merry Xmas Card | Pet Gift | Holiday Card",
        "requires": {},  # mesh render — no photo labels needed
    },
    "happy_holidays": {
        "label": "Happy Holidays card",
        "message": "Happy Holidays",
        "sub": "love, [pet name]",
        "source": "mesh",
        "theme": "christmas",
        "price_cents": 799,
        "sizes": ["A6", "5x7"],
        "tags": ["holiday card", "personalised card", "pet gift", "christmas", "custom dog"],
        "blurb": "Neutral holiday greeting with your pet's mesh render.",
        "etsy_title": "Personalised Holiday Card | Custom Pet Card | Happy Holidays | Dog Christmas Card | Pet Gift",
        "requires": {},  # mesh render — no photo labels needed
    },
    "thank_you": {
        "label": "Thank you card",
        "message": "Thank you",
        "sub": "— [pet name]",
        "source": "mesh",
        "theme": "everyday",
        "price_cents": 699,
        "sizes": ["A6", "5x7"],
        "tags": ["thank you card", "personalised pet", "custom card", "dog thank you"],
        "blurb": "Thank-you card starring your pet's 3D render.",
        "etsy_title": "Personalised Thank You Card | Custom Dog Card | Pet Thank You | Custom Pet Gift",
        "requires": {},  # mesh render — no photo labels needed
    },
    "happy_birthday": {
        "label": "Birthday card",
        "message": "Happy Birthday",
        "sub": "[pet name] says woof",
        "source": "mesh",
        "theme": "birthday",
        "price_cents": 799,
        "sizes": ["A6", "5x7"],
        "tags": ["birthday card", "personalised pet", "dog birthday", "custom card"],
        "blurb": "Birthday card with your pet's mesh render.",
        "etsy_title": "Personalised Dog Birthday Card | Custom Pet Birthday | Birthday Gift | Pet Card",
        "requires": {},  # mesh render — no photo labels needed
    },
    "real_photo": {
        "label": "Your photo card",
        "message": "Merry Xmas",
        "sub": "with love",
        "source": "upload",        # customer PNG/JPEG — no mesh required
        "theme": "christmas",
        "price_cents": 699,
        "sizes": ["A6", "5x7"],
        "tags": ["photo card", "custom photo card", "personalised card", "christmas photo"],
        "blurb": "Print your own photo on a greeting card — no 3D needed.",
        "etsy_title": "Personalised Photo Card | Custom Christmas Card | Photo Greeting Card | Pet Photo Card",
        "requires": {"solos": 1, "min_face_score": 0.5},  # any good single-subject shot
    },
}

# ── Etsy listing packs (title/tag/sizing — patterns from prx0r/oddhobbies) ──
# Photo strategy adapted from oddhobbies/shop/ETSY-SETUP.md (10 slots).
ETSY_PHOTO_SLOTS = [
    "hero shot (product on clean surface)",
    "in-use / lifestyle",
    "scale reference (next to everyday object)",
    "all variants (coats, hats, sizes)",
    "detail close-up (loop, texture, print)",
    "packaging",
    "size diagram with measurements",
    "personalisation example (name / message)",
    "bundle shot",
    "mesh / 3D viewer still",
]

ETSY_LISTINGS: dict[str, dict] = {
    "ornament": {
        "product_id": "ornament",
        "title": "Personalised Pet Ornament | Custom Dog Christmas Bauble | 3D Printed Pet Gift | Pet Ornament | Holiday Decor",
        "price_cents": 1299,
        "price_band": "impulse/treat",
        "currency": "GBP",
        "sizes": [
            {"id": "std", "label": "Standard", "height_mm": 80, "hole_mm": 5.0,
             "weight_g": "50–120", "note": "printed loop · ribbon + box"},
        ],
        "materials": "PLA+ · printed loop (no metal) · single-colour or multi-colour quote",
        "personalization": ["pet name on request", "coat colour", "santa hat addon"],
        "processing_days": "3–7",
        "ships_from": "UK print farm",
        "tags": ["personalised pet ornament", "dog christmas gift", "custom bauble",
                 "3d printed pet", "christmas ornament", "pet memorial ornament"],
        "blurb": (
            "One photo of your pet becomes a 3D-printed Christmas ornament with a printed "
            "hanging loop (never metal). Same mesh as our keychains and cards — upload once."
        ),
        "photo_slots": ETSY_PHOTO_SLOTS,
        "fulfilment": "print_farm",
        "source_repo": "prx0r/oddhobbies ETSY-SETUP + ALL-PRODUCTS sizing patterns",
    },
    "keychain": {
        "product_id": "keychain",
        "title": "Personalised Pet Keychain | Custom Dog Keyring | 3D Printed Key Chain | Pet Gift | Dog Keychain",
        "price_cents": 1499,
        "price_band": "treat",
        "currency": "GBP",
        "sizes": [
            {"id": "std", "label": "Standard", "height_mm": 80, "hole_mm": 4.0,
             "weight_g": "30–80", "note": "printed loop + printed ring · backing card"},
            {"id": "small", "label": "Small", "height_mm": 60, "hole_mm": 4.0,
             "weight_g": "20–50", "note": "pocket size"},
        ],
        "materials": "PLA+ · printed plastic ring (no metal) · backing card",
        "personalization": ["pet name", "coat colour"],
        "processing_days": "3–7",
        "ships_from": "UK print farm",
        "tags": ["personalised dog keychain", "custom keyring", "3d printed keychain",
                 "pet keychain", "christmas keychain", "pet gift"],
        "blurb": (
            "Same design as the ornament, smaller. Printed loop + printed plastic ring — "
            "POD-safe, no metal split ring required."
        ),
        "photo_slots": ETSY_PHOTO_SLOTS,
        "fulfilment": "print_farm",
        "source_repo": "prx0r/oddhobbies ETSY-SETUP + ALL-PRODUCTS sizing patterns",
    },
    "croc_tag": {
        "product_id": "croc_tag",
        "title": "Personalised Pet Croc Charm | Crocs Tag Pin | Custom Dog Jibbitz | Pet Shoe Charm | Croc Accessory",
        "price_cents": 899,
        "price_band": "impulse",
        "currency": "GBP",
        "sizes": [
            {"id": "std", "label": "Standard", "height_mm": 28, "pin_diameter_mm": 12,
             "weight_g": "3–8", "note": "printed pin stem · pops into Croc holes"},
        ],
        "materials": "PLA+ · printed pin stem (no metal hardware required)",
        "personalization": ["pet name", "coat colour"],
        "processing_days": "3–7",
        "ships_from": "UK print farm",
        "tags": ["croc charm", "crocs jibbitz", "personalised croc pin", "dog shoe charm",
                 "custom crocs accessory", "pet croc tag", "croc pin"],
        "blurb": (
            "Tiny 3D-printed charm of your pet that pops into Croc holes — Jibbitz-style. "
            "Printed pin stem, no metal. Same mesh as ornaments and keychains."
        ),
        "photo_slots": ETSY_PHOTO_SLOTS,
        "fulfilment": "print_farm",
        "source_repo": "owner brainwave 2026-10-02 + oddhobbies ETSY-SETUP sizing pattern",
    },
    "brick": {
        "product_id": "brick",
        "title": "Personalised Brick Figure | Custom Pet Desk Toy | 3D Printed Minifig | Geek Gift | LEGO-Style Pet Figure",
        "price_cents": 1999,
        "price_band": "treat/gift",
        "currency": "GBP",
        "sizes": [
            {"id": "std", "label": "Standard", "height_mm": 75,
             "weight_g": "80–150", "note": "desk brick figure · no hardware"},
        ],
        "materials": "PLA+ · single-colour print · multi-colour quote on request",
        "personalization": ["pet name", "coat colour (preview grade)"],
        "processing_days": "3–7",
        "ships_from": "UK print farm",
        "tags": ["personalised brick figure", "custom pet toy", "3d printed minifig",
                 "desk figure", "geek pet gift", "lego style pet"],
        "blurb": (
            "Your pet as a 75 mm brick-style desk figure — minifig proportions, "
            "printed as one piece. Same photo-to-mesh pipeline as our ornaments."
        ),
        "photo_slots": ETSY_PHOTO_SLOTS,
        "fulfilment": "print_farm",
        "source_repo": "brick line live 2026-10-03 · mesh msh_a984c413 · Creative Lab brick-figure",
    },
    "gift_card": {
        "product_id": "gift_card",
        "title": "OddHobb Gift Card | Digital Gift Card | Personalised Pet Products | eGift Card | Instant Delivery",
        "price_cents": 2500,
        "price_band": "gift",
        "currency": "GBP",
        "sizes": [
            {"id": "10", "label": "£10", "amount_cents": 1000, "note": "digital code"},
            {"id": "25", "label": "£25", "amount_cents": 2500, "note": "digital code"},
            {"id": "50", "label": "£50", "amount_cents": 5000, "note": "digital code"},
        ],
        "materials": "Digital delivery · redeemable on OddHobb",
        "personalization": ["gift message"],
        "processing_days": "0–1",
        "ships_from": "email",
        "tags": ["gift card", "digital gift card", "pet lover gift", "custom gift card",
                 "instant delivery", "odd hobby gift"],
        "blurb": "Digital credit toward personalised pet products. Instant email delivery.",
        "photo_slots": ["gift card design mockup", "how-to-redeem graphic"],
        "fulfilment": "digital",
        "source_repo": "prx0r/oddhobbies ETSY-SETUP",
    },
    "xmas_card": {
        "product_id": "xmas_card",
        "title": "Personalised Pet Christmas Card | Custom Dog Xmas Card | Merry Xmas Card | Pet Holiday Card | Photo Card",
        "price_cents": 799,
        "price_band": "impulse",
        "currency": "GBP",
        "sizes": [
            {"id": "A6", "label": "A6", "mm": "105 × 148", "price_cents": 399},
            {"id": "5x7", "label": "5×7", "mm": "127 × 178", "price_cents": 799},
            {"id": "A5", "label": "A5", "mm": "148 × 210", "price_cents": 999},
        ],
        "materials": "300–350gsm matte · full-colour print · envelope (5×7)",
        "personalization": ["pet name", "message", "mesh style OR your own photo"],
        "processing_days": "2–5",
        "ships_from": "UK print farm",
        "tags": ["personalised christmas card", "custom dog card", "merry xmas card",
                 "pet christmas gift", "photo christmas card", "holiday greeting"],
        "blurb": (
            "Christmas card with your pet — 3D mesh render or your own photo. "
            "Sizes A6 / 5×7 / A5. Print & post from the UK."
        ),
        "photo_slots": ETSY_PHOTO_SLOTS,
        "fulfilment": "print_farm",
        "source_repo": "prx0r/oddhobbies ETSY-SETUP photo strategy + SEO sizing",
    },
    "wrapping_paper": {
        "product_id": "wrapping_paper",
        "title": "Personalised Pet Wrapping Paper | Custom Dog Gift Wrap | Pet Face Xmas Wrap | Christmas Gift Wrap | Photo Wrapping Paper",
        "price_cents": 1499,
        "price_band": "treat/gift",
        "currency": "GBP",
        "sizes": [
            {"id": "sheet", "label": "Single sheet 50×70cm", "mm": "500 × 700",
             "sku": "WRAP-1-50X70", "price_cents": 1499,
             "note": "one FSC sheet — wraps 1–2 small gifts"},
            {"id": "large", "label": "Large sheet 75×90cm", "mm": "750 × 900",
             "sku": "WRAP-1-75X90", "price_cents": 1999,
             "note": "one large FSC sheet — wraps big boxes"},
            {"id": "roll", "label": "Roll 70cm × 1m", "mm": "700 × 1000",
             "sku": "WRAP-ROL-70X100", "price_cents": 2499,
             "note": "FSC roll — the whole Christmas pile"},
        ],
        "materials": "FSC gift wrap paper · full-colour print · ships UK/EU/US",
        "personalization": ["your pet's face tiled", "berry / forest / cream background"],
        "processing_days": "2–5",
        "ships_from": "UK print farm",
        "tags": ["personalised wrapping paper", "custom dog gift wrap",
                 "pet face wrapping paper", "christmas gift wrap",
                 "photo wrapping paper", "funny dog gift wrap"],
        "blurb": (
            "Your pet's face, tiled all over real gift wrap. One photo becomes "
            "a repeating half-drop pattern with gold stars — berry, forest or cream. "
            "Printed on demand, ships from the UK."
        ),
        "photo_slots": ETSY_PHOTO_SLOTS,
        "fulfilment": "print_farm",
        "source_repo": "Prodigi WRAP range · verified live 2026-10-10 (check+quote, no order)",
    },
}

# Machine-readable Etsy pack for agents / Shopify / listing tools
ETSY_SOURCE_NOTE = (
    "Listing patterns + photo-slot strategy adapted from prx0r/oddhobbies "
    "(docs/ETSY-SETUP.md, KILLER-PRODUCTS.md, ALL-PRODUCTS.md). "
    "OddHobb sizes from docs/balance.md + PRODIGI/SEO pack."
)

# ── Meshy Creative Lab catalogue (docs.meshy.ai · verified 2026-10-02) ──
# Ship-with-Meshy path: photo → prototype → build → print (ours or Meshy Order Print).
# Costs in credits. ALWAYS ask the human before any spend. Ledger: data/meshy_credits.jsonl
MESHY_CATALOG: dict[str, dict] = {
    "figure": {
        "label": "Chibi figure",
        "api": "creative-lab/figure/v1",
        "prototype_credits": 6,
        "build_credits": 30,
        "total_credits": 36,
        "input": "photo",
        "output": "GLB + OBJ/MTL",
        "oddhobb_use": "Primary pet body → ornament / keychain / croc / brick",
        "notes": "Our dog mesh came from this track (manual webapp + API).",
    },
    "brick_figure": {
        "label": "Brick figure",
        "api": "creative-lab/brick-figure/v1",
        "prototype_credits": 6,
        "build_credits": 30,
        "total_credits": 36,
        "input": "photo",
        "output": "GLB",
        "oddhobb_use": "Desk brick SKU (~75 mm) — parent meshes may also be user-generated",
        "notes": "Minifig-style; good for parents-as-bricks wedge.",
    },
    "vinyl_figure": {
        "label": "Vinyl figure",
        "api": "creative-lab/vinyl-figure/v1",
        "prototype_credits": 6,
        "build_credits": 30,
        "total_credits": 36,
        "input": "photo",
        "output": "GLB",
        "oddhobb_use": "Collector vinyl SKU (Funko-adjacent) — later product line",
        "notes": "Toy-style collectible body.",
    },
    "keychain_cl": {
        "label": "Keychain (Creative Lab medallion)",
        "api": "creative-lab/keychain/v1",
        "prototype_credits": 6,
        "build_credits": 30,
        "total_credits": 36,
        "input": "photo",
        "output": "GLB relief",
        "oddhobb_use": "Optional badge/keychain *medallion* (depth relief) — not our 3D pet keychain",
        "notes": "Fixed ~50 mm badge shape. Our pet keychain stays figure-track + printed ring.",
        "size_mm": 50,
    },
    "fridge_magnet": {
        "label": "Fridge magnet",
        "api": "creative-lab/fridge-magnet/v1",
        "prototype_credits": 6,
        "build_credits": 30,
        "total_credits": 36,
        "input": "photo",
        "output": "GLB relief + flat back",
        "oddhobb_use": "New SKU — pet face relief magnet",
        "notes": "Colourized depth relief, magnetic back.",
    },
    "lamp": {
        "label": "Lamp / lampshade",
        "api": "creative-lab/lamp/v1",
        "prototype_credits": 30,
        "build_credits": 6,
        "total_credits": 36,
        "input": "photo (or text in webapp)",
        "output": "STL lampshade + optional base (Bambu MH001 60 mm fixture)",
        "oddhobb_use": "New SKU — glowing pet lamp (Meshy Order Print available)",
        "notes": "Build is processor: hollow, open bottom, fixture plate. diameter_mm options.",
        "fixture_presets": ["bambu_mh001_60mm", "none"],
    },
    "keycap": {
        "label": "Keycap (Cherry MX 1u)",
        "api": "creative-lab/keycap/v1",
        "prototype_credits": 12,
        "build_credits": 50,
        "total_credits": 62,
        "input": "photo",
        "output": "GLB keycap",
        "oddhobb_use": "Desk collectible / keyboard wedge",
        "notes": "head_size_mm 10–40 (default 23). Costs more than other CL products.",
        "base_model": "cherry-mx-1x1-r1",
    },
    "fidget_pixel": {
        "label": "Fidget pixel",
        "api": "creative-lab/fidget-pixel/v1",
        "prototype_credits": 6,
        "build_credits": 30,
        "total_credits": 36,
        "input": "photo",
        "output": "GLB",
        "oddhobb_use": "Impulse desk toy SKU",
        "notes": "Printable fidget from photo.",
    },
    "fidget_collapsible": {
        "label": "Collapsible fidget",
        "api": "creative-lab/fidget-collapsible/v1",
        "prototype_credits": 0,
        "build_credits": 6,
        "total_credits": 6,
        "input": "photo",
        "output": "GLB",
        "oddhobb_use": "Cheap impulse SKU",
        "notes": "Single-stage generation (6 cr build only).",
    },
    # Non-Creative-Lab Meshy extras (still shippable)
    "image_to_3d": {
        "label": "Image to 3D (generic)",
        "api": "image-to-3D",
        "prototype_credits": 0,
        "build_credits": 0,
        "total_credits": None,  # varies; check pricing.md
        "input": "photo",
        "output": "GLB textured",
        "oddhobb_use": "Fallback body if Creative Lab shape is wrong",
        "notes": "Under /openapi/v1/image-to-3D — not Creative Lab.",
    },
    "multicolor_print": {
        "label": "3D Print multi-color (3MF)",
        "api": "3D Print Multi-Color",
        "prototype_credits": 0,
        "build_credits": 10,
        "total_credits": 10,
        "input": "textured model",
        "output": "3MF",
        "oddhobb_use": "Convert pet texture → multi-colour print file",
        "notes": "Printability analyze is free; repair is 10 cr.",
    },
}

MESHY_SHIP_NOTE = (
    "Yes — Meshy can ship physical prints (Order Print, ~2–3 weeks, 24 countries, "
    "free shipping in US/CA/DE/ES/FR/IT/BR/CN/JP). We can also print locally via "
    "Makr3D/Prodigi. Generate with Meshy Creative Lab, fulfil via us or them."
)

# ── Google sign-in ──────────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
# Public base URL for anything a third party must fetch without a token
# (feed image_link, Shopify image src). No secrets ever appear in these URLs.
# NOTE: .env currently pins this to https://pog.pet (kept stable for the
# Google OAuth callback in auth.py). Flip .env to https://oddhobb.com when
# the Google Cloud console redirect URI is updated — feeds follow it.
PUBLIC_BASE = os.environ.get("PUBLIC_BASE", "https://oddhobb.com")

# ── multi-brand: one codebase, many storefronts ─────────────────────
# One Flask app serves every brand host. Brand strings NEVER live in
# frontend text: GET /api/brand answers per request Host, and premesh
# zones follow the request host.
# store_id MUST match oddhobbies commerce + bgraph organiser.
# Domains: grimoirer.com is primary for Grimoirer (ochema.co kept as alias).
BRANDS = {
    "oddhobb.com": {
        "brand": "oddhobb",
        "store_id": "oddhobb",
        "tagline": "what odd thing shall we make you?",
        "support": "support@oddhobb.com",
        "commerce_pack": "oddhobbies/stores/oddhobb",
        "bgraph": "bgraph/registry/brands/oddhobb.json",
    },
    "pog.pet": {
        "brand": "oddhobb",
        "store_id": "oddhobb",
        "tagline": "what odd thing shall we make you?",
        "support": "support@oddhobb.com",
        "note": "legacy alias for oddhobb",
    },
    "ochema.co": {
        "brand": "grimoirer",
        "store_id": "grimoirer",
        "tagline": "your practice, your way.",
        "support": "support@grimoirer.com",
        "note": "alias — prefer grimoirer.com",
    },
    "grimoirer.com": {
        "brand": "grimoirer",
        "store_id": "grimoirer",
        "tagline": "your practice, your way.",
        "support": "support@grimoirer.com",
        "commerce_pack": "oddhobbies/stores/grimoirer",
        "bgraph": "bgraph/registry/brands/grimoirer.json",
    },
    "stonedoorway.com": {
        "brand": "stonedoorway",
        "store_id": "stonedoorway",
        "tagline": "TODO thesis",
        "support": "support@stonedoorway.com",
        "commerce_pack": "oddhobbies/stores/stonedoorway",
        "bgraph": "bgraph/registry/brands/stonedoorway.json",
        "status": "scaffold",
    },
}
DEFAULT_BRAND_HOST = "oddhobb.com"


def brand_for(host: str) -> dict:
    """Brand record for a request Host. Subdomains inherit the parent brand;
    unknown hosts fall back to the default (never 404 on branding)."""
    h = (host or "").split(":")[0].lower()
    if h.startswith("www."):
        h = h[4:]
    if h not in BRANDS:
        parent = ".".join(h.split(".")[-2:])
        h = parent if parent in BRANDS else DEFAULT_BRAND_HOST
    b = BRANDS[h]
    return {"host": h, "domain": h, **b}

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
    "cards:read":    "See card designs, gallery, shelf and previews",
    "cards:create":   "Save cards, render, re-roll and attach art",
    "cards:order":    "Reserve and checkout cards (£7.99 fixed)",
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
    "greeting_card": {"label": "Greeting Card",   "price_cents": 299,  "sku": "CLASSIC-GRE-FEDR-7X5-BLA", "sku_note": "Classic 5x7 portrait, 127x178mm, verified live",   "shape": "card",   "free": False},
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
    "wrapping_paper": {"label": "Wrapping Paper", "price_cents": 1499,
                       "sku": "WRAP-1-50X70", "sku_attrs": {},
                       "requires": {"solos": 1, "min_face_score": 0.5},  # hero tile source
                       "alt_skus": {"large_sheet": "WRAP-1-75X90",
                                    "sheet_3pack": "WRAP-3-50X70",
                                    "roll": "WRAP-ROL-70X100"},
                       "sku_note": "WRAP-1-50X70 single 50x70cm sheet · verified live 2026-10-10 (alt: 75X90 large, 3-pack, 70x1m roll)",
                       "shape": "paper", "free": False},
}

# ── SEO / agent-discovery pack (docs/seo.md) ─────────────────────────
# The 8 Google AI feed attributes per product. Keys align with
# PRODIGI_PRODUCTS / PRODUCTS ids. Consumed by:
#   GET /api/seo/products.json  (public, full pack)
#   GET /api/feeds/google.xml   (highlights+details in description)
#   GET /api/feeds/shopify.json (Q&A in body_html, tags)
#   GET /guides/<id>            (crawlable companion guide)
#   site/index.html JSON-LD     (ItemList + Offers)
SEO: dict[str, dict] = {
    "greeting_card": {
        "highlight": "Personalised;3D pet render;Printed & posted;Gift-ready",
        "details": "Size:A6|Paper:300gsm matte|Print:full-colour|Origin:UK print farm",
        "variants": "Theme:Classic|Theme:Birthday|Theme:Holiday",
        "item_group": "Personalised Pet Cards",
        "related": "Often bought with:postcard,sticker,wrapping_paper",
        "qa": [
            ("What is a personalised pet greeting card?",
             "A greeting card printed with a 3D render of your own pet, ready to send to family and friends."),
            ("Can I use any pet photo?",
             "Yes — upload one clear photo. We turn it into a 3D character and print it on the card."),
            ("How long does shipping take?",
             "1–3 business days production, then 5–10 days worldwide shipping."),
            ("Is the card blank inside?",
             "Yes — blank inside so you can write your own message."),
            ("What paper is it printed on?",
             "300gsm matte fine-art stock, printed full colour."),
        ],
        "docs": ["/guides/greeting_card"],
    },
    "postcard": {
        "highlight": "Personalised;A6 format;Affordable gift;Mail-ready",
        "details": "Size:A6|Paper:350gsm|Print:full-colour|Finish:matte",
        "variants": "Theme:Classic|Theme:Pet Portrait",
        "item_group": "Personalised Pet Cards",
        "related": "Often bought with:greeting_card,sticker",
        "qa": [
            ("What size is the personalised postcard?",
             "A6 — standard postcard size, fits most frames and mail slots."),
            ("Can I send it internationally?",
             "Yes — we ship worldwide; postcard mail rates apply at your post office."),
            ("Is it the same render as the cards?",
             "Yes — one pet photo becomes every product in your order."),
        ],
        "docs": ["/guides/postcard"],
    },
    "sticker": {
        "highlight": "Kiss-cut;Waterproof vinyl;Pet portrait;Pack of sheets",
        "details": "Size:A5 sheet|Material:vinyl|Cut:kiss-cut|Pack:multi",
        "variants": "Theme:Classic|Theme:Chibi",
        "item_group": "Personalised Pet Stickers",
        "related": "Often bought with:mug,tote,notebook",
        "qa": [
            ("Are the stickers waterproof?",
             "Yes — vinyl kiss-cut stickers handle water and light outdoor use."),
            ("What comes in a sticker pack?",
             "Multiple kiss-cut sheets featuring your pet's 3D render."),
            ("Can I put them on a laptop or water bottle?",
             "Yes — vinyl adheres well to laptops, bottles, notebooks and cases."),
        ],
        "docs": ["/guides/sticker"],
    },
    "framed_print": {
        "highlight": "Framed wall art;Museum-quality print;Personalised pet portrait;Gift",
        "details": "Sizes:12x16 to 24x36|Frame:wood or canvas|Print:giclée|Glass:optional",
        "variants": "Finish:Framed|Finish:Canvas|Finish:Metal",
        "item_group": "Personalised Pet Wall Art",
        "related": "Often bought with:poster,photo_tile,cushion",
        "qa": [
            ("What is a framed personalised pet print?",
             "A wall-art print of your pet's 3D render, available framed, on canvas, or on metal."),
            ("What sizes are available?",
             "From 12x16 up to 24x36 inches — choose at checkout."),
            ("How do I care for the print?",
             "Dust with a dry cloth; keep out of direct prolonged sunlight."),
        ],
        "docs": ["/guides/framed_print"],
    },
    "poster": {
        "highlight": "Wall poster;Personalised;Bright print;Easy framing",
        "details": "Sizes:A4 to A2|Paper:200gsm satin|Print:full-colour",
        "variants": "Size:A4|Size:A3|Size:A2",
        "item_group": "Personalised Pet Wall Art",
        "related": "Often bought with:framed_print,photo_tile",
        "qa": [
            ("Is the poster personalised?",
             "Yes — printed with your pet's 3D character render."),
            ("Does it come framed?",
             "Posters ship rolled in a tube; frames sold separately or use a standard size."),
        ],
        "docs": ["/guides/poster"],
    },
    "photo_tile": {
        "highlight": "Ceramic tile;Personalised;Home decor;Easy hang",
        "details": "Size:6x6 or 8x8|Material:ceramic|Finish:glossy|Hang:adhesive or hook",
        "variants": "Size:6x6|Size:8x8",
        "item_group": "Personalised Pet Home Decor",
        "related": "Often bought with:cushion,mug",
        "qa": [
            ("What is a personalised photo tile?",
             "A ceramic tile printed with your pet's 3D render — wall décor or shelf piece."),
            ("How do I hang it?",
             "Use the included adhesive strip or a standard picture hook."),
        ],
        "docs": ["/guides/photo_tile"],
    },
    "cushion": {
        "highlight": "Home décor;Personalised pet art;Soft cover;Gift",
        "details": "Size:45x45cm|Cover:polyester|Fill:included|Print:sublimation",
        "variants": "Colour:white|Colour:cream",
        "item_group": "Personalised Pet Home Decor",
        "related": "Often bought with:mug,photo_tile,tote",
        "qa": [
            ("Is the cushion cover removable?",
             "Yes — zip cover, machine washable cold."),
            ("Does it include the filler?",
             "Yes — cushion arrives ready to use."),
        ],
        "docs": ["/guides/cushion"],
    },
    "mug": {
        "highlight": "Dishwasher-safe;Personalised pet mug;Gift;Daily use",
        "details": "Size:11oz|Material:ceramic|Print:sublimation|Dishwasher:yes",
        "variants": "Colour:white|Colour:black",
        "item_group": "Personalised Pet Drinkware",
        "related": "Often bought with:sticker,tote,notebook",
        "qa": [
            ("Is the mug dishwasher safe?",
             "Yes — ceramic with sublimation print handles dishwasher and microwave."),
            ("What size is the mug?",
             "Standard 11oz ceramic mug."),
        ],
        "docs": ["/guides/mug"],
    },
    "tote": {
        "highlight": "Reusable bag;Personalised;Eco-friendly;Gift",
        "details": "Size:38x42cm|Material:cotton canvas|Strap:long|Print:full-colour",
        "variants": "Natural|Black",
        "item_group": "Personalised Pet Accessories",
        "related": "Often bought with:mug,sticker,notebook",
        "qa": [
            ("What is the tote made from?",
             "Cotton canvas with long shoulder straps and full-colour print."),
            ("Can I wash it?",
             "Spot clean or gentle cold wash; hang dry."),
        ],
        "docs": ["/guides/tote"],
    },
    "notebook": {
        "highlight": "Custom cover;Personalised;Stationery;Gift",
        "details": "Size:A5|Pages:96|Paper:ruled|Cover:soft-touch",
        "variants": "Ruled|Dotted",
        "item_group": "Personalised Pet Stationery",
        "related": "Often bought with:sticker,greeting_card",
        "qa": [
            ("Can I choose ruled or dotted pages?",
             "Yes — pick at checkout; cover is always your pet's render."),
            ("What size is the notebook?",
             "A5 — fits most bags and desk organisers."),
        ],
        "docs": ["/guides/notebook"],
    },
    "jigsaw": {
        "highlight": "Custom puzzle;Personalised;Family gift;Printed lid",
        "details": "Pieces:100 or 500|Size:approx 48x34cm|Lid:full print|Box:included",
        "variants": "Pieces:100|Pieces:500",
        "item_group": "Personalised Pet Games",
        "related": "Often bought with:greeting_card,poster",
        "qa": [
            ("How many pieces does the jigsaw have?",
             "Choose 100 or 500 pieces — both use the same personalised artwork."),
            ("Is the box printed too?",
             "Yes — the lid carries the full pet render."),
        ],
        "docs": ["/guides/jigsaw"],
    },
    "canvas": {
        "highlight": "Stretched canvas;Gallery wrap;Personalised;Wall art",
        "details": "Size:10x10in|Material:canvas|Wrap:gallery|Ready:to hang",
        "variants": "Wrap:White|Wrap:Black",
        "item_group": "Personalised Pet Wall Art",
        "related": "Often bought with:framed_print,poster",
        "qa": [
            ("What is a stretched canvas print?",
             "Your pet's 3D render printed on canvas and gallery-wrapped on a wooden frame — ready to hang."),
            ("What size is it?",
             "10×10 inches in this listing; larger sizes available on request."),
        ],
        "docs": ["/guides/canvas"],
    },
    "wrapping_paper": {
        "highlight": "Personalised gift wrap;Pet render;Roll;Gift-ready",
        "details": "Size:70x50cm sheets|Paper:120gsm|Print:full-colour|Pack:multi",
        "variants": "Classic|Chibi",
        "item_group": "Personalised Pet Gift Wrap",
        "related": "Often bought with:greeting_card,sticker",
        "qa": [
            ("Is the wrapping paper personalised?",
             "Yes — printed with your pet's 3D character."),
            ("How many sheets per pack?",
             "Multiple A2-equivalent sheets per pack — enough for several gifts."),
        ],
        "docs": ["/guides/wrapping_paper"],
    },
    "figurine": {
        "highlight": "3D printed;Chibi style;Personalised;Collectible",
        "details": "Material:PLA+|Height:approx 80mm|Base:magnetic option|Finish:hand-finished",
        "variants": "Style:Chibi|Style:Realistic",
        "item_group": "Personalised Pet Figurines",
        "related": "Often bought with:bauble,greeting_card",
        "qa": [
            ("What is a personalised pet figurine?",
             "A 3D-printed chibi figure made from your pet's photo, printed on a Bambu farm in the UK."),
            ("How tall is the figurine?",
             "Approximately 80mm — desk and shelf sized."),
            ("Can I choose the style?",
             "Yes — chibi or realistic-leaning styles are available."),
        ],
        "docs": ["/guides/figurine"],
    },
    "video": {
        "highlight": "AI talking video;Free preview;Personalised;Shareable",
        "details": "Length:15–45s|Format:MP4|Voice:edge-tts|Watermark:free tier",
        "variants": "Talent:comedy|Talent:dance|Talent:singing",
        "item_group": "Personalised Pet Videos",
        "related": "Often bought with:comedy_set,card",
        "qa": [
            ("What is a personalised pet video?",
             "A short MP4 where your pet's 3D character performs a comedy or talent bit you write a topic for."),
            ("Is the free video watermarked?",
             "Yes — free tier includes a watermark; paid tiers remove it."),
            ("How long are the videos?",
             "Typically 15–45 seconds, depending on the script."),
        ],
        "docs": ["/guides/video"],
    },
}

# ── GEO expansion (docs/seo.md — target ~30 Q&A pairs per product) ────
# Shared answer bank appended to every product's qa list so conversational
# AI has citable, specific answers. Product-specific pairs stay above.
_GEO_SHARED_QA = [
    ("What is OddHobb?",
     "OddHobb turns one pet photo into a 3D character, then prints that character on cards, prints, mugs, puzzles, figurines and videos."),
    ("How does OddHobb personalisation work?",
     "Upload one clear photo. We build a 3D model of your pet, then render it onto every product in your order — you only upload once."),
    ("Where are OddHobb products made?",
     "Prints and physical goods are produced on UK print farms; 3D figurines are printed on a Bambu farm in the UK. Videos are rendered on our stack."),
    ("How long does OddHobb shipping take?",
     "1–3 business days production, then 5–10 days worldwide shipping depending on destination."),
    ("Does OddHobb ship internationally?",
     "Yes — worldwide shipping from the UK."),
    ("Is OddHobb free to try?",
     "Yes. The free tier includes a small daily allowance of 3D sculpts and watermarked videos so you can see your pet before buying."),
    ("What photo works best for OddHobb?",
     "A clear, well-lit photo of your pet facing the camera. Avoid heavy blur, harsh shadows and group shots."),
    ("Can I use OddHobb for a gift?",
     "Yes — personalised pet products are common gifts. Upload the photo, pick products, and we ship to you or directly to the recipient."),
    ("What is a personalised pet figurine?",
     "A small 3D-printed figure made from your pet's photo — typically chibi or realistic-leaning, desk or shelf sized."),
    ("What is a pet photo to 3D service?",
     "A service that converts a 2D pet photo into a 3D model, which can be printed as a figurine or rendered onto other products."),
    ("OddHobb vs a traditional pet portrait?",
     "A traditional portrait is hand-drawn or painted from photos. OddHobb builds a 3D model once and reuses it across many printed products and videos."),
    ("OddHobb vs print-on-demand pet mugs?",
     "Generic POD mugs print a flat photo. OddHobb prints a 3D character render of your pet, and the same character can appear on every item in the order."),
    ("OddHobb vs a 3D scanning service?",
     "3D scanning usually needs the live pet or special equipment. OddHobb starts from an ordinary phone photo."),
    ("What file formats does OddHobb use?",
     "Photos in JPEG or PNG. Outputs include GLB/USDZ meshes, PNG mockups, MP4 videos and print-ready PDFs depending on the product."),
    ("Can I see my pet in 3D before buying?",
     "Yes — the free sculpt tier lets you preview the 3D character before you order physical products."),
    ("Does OddHobb use AI?",
     "Yes — AI builds the 3D character from your photo and can write short performance scripts for free-tier videos. Humans still run quality checks."),
    ("Is my pet photo private?",
     "Photos are stored privately for fulfilment. Public marketing images never include your pet. Contact support to delete your data."),
    ("What sizes are OddHobb prints?",
     "Cards A6; posters A4–A2; framed prints 12x16 to 24x36; canvas 10x10 in the standard listing — larger sizes on request."),
    ("What materials are OddHobb products?",
     "Depends on the product: 300gsm card, vinyl stickers, ceramic mugs, cotton canvas totes, PLA+ for figurines, and more — each guide lists specs."),
    ("How do I care for OddHobb products?",
     "Dust prints with a dry cloth, machine-wash removable cushion covers cold, dishwasher-safe mugs are fine — see each product guide."),
    ("Can I order OddHobb products in bulk?",
     "Bulk and gift sets are supported via support@oddhobb.com — mention quantity and deadline."),
    ("What payment methods does OddHobb accept?",
     "Card checkout via Shopify. Cryptocurrency/Tor private checkout is research-only and not live."),
    ("How do I contact OddHobb support?",
     "Email support@oddhobb.com — same inbox is on every brand domain."),
    ("Can I sell OddHobb products on Etsy?",
     "OddHobb is the brand behind the storefront; wholesale and partner queries go to support."),
    ("What is GEO in marketing?",
     "Generative Engine Optimisation — writing structured, citable content so AI assistants like ChatGPT and Google AI recommend you inside answers."),
    ("Why does OddHobb publish Q&A pairs?",
     "Google Merchant Center and other AI surfaces use pre-written Q&A to answer shopper questions in AI Mode and chat assistants."),
    ("What is a product highlight?",
     "A short benefit statement (not a spec) that Google surfaces across AI-driven shopping results — for example 'Personalised; 3D printed; Gift-ready'."),
    ("How do I track an OddHobb order?",
     "Tracking is emailed when the order ships from the UK print farm. Reply to that email if anything looks wrong."),
    ("Can I change my pet's 3D style later?",
     "Yes — new styles (chibi vs realistic-leaning) can be sculpted from the same photo; earlier orders stay as produced."),
    ("What if my pet looks different from the photo?",
     "Send a clearer reference photo to support and we can re-sculpt; physical orders already printed follow the original artwork unless defective."),
]


def expand_seo_qa() -> None:
    """Append the GEO shared bank to every product that has a SEO pack."""
    for pack in SEO.values():
        existing = {(q.lower(), a.lower()) for q, a in pack.get("qa", [])}
        for q, a in _GEO_SHARED_QA:
            if (q.lower(), a.lower()) not in existing:
                pack.setdefault("qa", []).append((q, a))


expand_seo_qa()

# GEO knowledge pages (definitions + comparisons) for AI crawlers
GEO_PAGES: dict[str, dict] = {
    "what-is-a-pet-figurine": {
        "title": "What is a personalised pet figurine?",
        "definition": (
            "A personalised pet figurine is a small 3D-printed figure made "
            "from a photo of your own pet. OddHobb builds a 3D character "
            "from one upload, then prints it as a chibi or realistic-leaning "
            "figurine you can keep on a desk or shelf."
        ),
        "sections": [
            ("How does it work?",
             "Upload one clear photo. OddHobb sculpts a 3D model, you "
             "preview it on the free tier, then order a print. The same "
             "model can also appear on cards, mugs and videos."),
            ("What is it made from?",
             "Figurines are 3D printed in PLA+ on a UK Bambu farm, then "
             "hand-finished. Magnetic bases are optional."),
            ("How big is it?",
             "The standard figurine is approximately 80mm tall — desk and "
             "shelf sized."),
        ],
    },
    "oddhobb-vs-pet-portraits": {
        "title": "OddHobb vs traditional pet portraits",
        "definition": (
            "Traditional pet portraits are hand-drawn or painted from photos. "
            "OddHobb builds a reusable 3D character from one photo and "
            "prints that character on many products — cards, prints, mugs, "
            "figurines and short videos."
        ),
        "sections": [
            ("Comparison",
             "table"),
            ("When to choose OddHobb",
             "You want matching gifts across a whole order, a free 3D preview "
             "before buying, and one upload instead of a commission wait."),
            ("When a traditional portrait is better",
             "You want a one-off fine-art piece in a specific medium "
             "(oil, watercolour) from a named artist."),
        ],
        "comparison": {
            "headers": ["Factor", "OddHobb", "Traditional portrait"],
            "rows": [
                ["Input", "One phone photo", "Photos + artist brief"],
                ["Output", "3D character on many products", "Single art piece"],
                ["Preview", "Free 3D sculpt tier", "Sketch/commission stages"],
                ["Turnaround", "Days (print + ship)", "Weeks–months"],
                ["Price band", "From a few GBP to print prices", "Usually higher per piece"],
                ["Reuse", "Same character on cards, mugs, video", "One artwork"],
            ],
        },
    },
    "how-personalised-pet-products-work": {
        "title": "How personalised pet products work",
        "definition": (
            "Personalised pet products take a photo of your animal and turn "
            "it into merchandise that already features them. OddHobb goes "
            "further: one photo becomes a 3D character that is reused across "
            "every product in the order."
        ),
        "sections": [
            ("The OddHobb flow",
             "Upload → free 3D sculpt preview → pick products (card, print, "
             "mug, puzzle, figurine, video) → checkout → UK production → "
             "worldwide shipping."),
            ("Why 3D beats a flat photo print",
             "A 3D character can be re-lit, re-posed and rendered onto new "
             "products later without re-sculpting from scratch."),
            ("Who it is for",
             "Pet owners, gift-givers, and anyone who wants a matching set "
             "rather than one-off print."),
        ],
    },
    "best-gifts-for-pet-owners": {
        "title": "Best gifts for pet owners",
        "definition": (
            "The best gifts for pet owners already feature their animal. "
            "OddHobb personalised cards, prints, mugs, puzzles and figurines "
            "are built from one photo of their pet."
        ),
        "sections": [
            ("Gift table", "table"),
            ("How to choose",
             "Pick by budget and use: cards for under £10, mugs and prints "
             "for desks and walls, figurines and puzzles for keepsakes."),
        ],
        "comparison": {
            "headers": ["Gift", "Price (GBP)", "Why it works"],
            "rows": [
                ["Greeting card", "7.99", "Personal, easy to post"],
                ["Postcard", "3.99", "Small and affordable"],
                ["Mug", "14.99", "Daily use with their pet on it"],
                ["Sticker sheet", "4.99", "Laptops, bottles, notebooks"],
                ["Stretched canvas", "20.32", "Wall art, gift-ready"],
                ["Chibi figurine", "19.99", "Keepsake from one photo"],
                ["Jigsaw puzzle", "18.99", "Activity gift for the household"],
            ],
        },
    },
}


API_TOKEN = os.environ.get("API_TOKEN", "")


# ── helper agent + company graph (agentcom/companygraph pattern) ─────
# bobdod is the main helper customers talk to on the storefront and the
# identity other agents meet via MCP. FACTS are derived from the live
# catalog config — never a second hand-maintained copy.
HELPER_AGENT = {
    "name": "bobdod",
    "role": "Store helper",
    "voice": "warm, direct, catalogue-obsessed",
    "traits": ["helpful", "knows every product", "no nonsense", "asks one good question"],
    "description": (
        "Main helper agent for OddHobb. Customers talk to bobdod on the "
        "storefront; agents meet the same identity via MCP. Backed by the "
        "company graph (products, policies, resources, capabilities)."
    ),
}


def company_products() -> list[dict]:
    """FACTS.products from the live catalog — prices in GBP."""
    out = []
    for pid, spec in {**PRODUCTS, **PRODIGI_PRODUCTS}.items():
        out.append({
            "id": pid,
            "name": spec.get("label", pid),
            "price_gbp": round(spec.get("price_cents", 0) / 100.0, 2),
            "free": bool(spec.get("free", False)),
            "source": spec.get("source", "prodigi"),
            "section": SECTION_OF.get(pid, "all"),
            "evidence": ["config.PRODUCTS/PRODIGI_PRODUCTS", "docs/seo.md SEO pack"],
        })
    return out


def company_graph() -> dict:
    """OddHobb CompanyGraph — FACTS / RESOURCES / CAPABILITIES + helper agent."""
    return {
        "company": {
            "legal_name": "OddHobb",
            "brand": "oddhobb",
            "domains": sorted(set(list(BRANDS.keys()) + ["pog.pet"])),
            "country": "GB",
            "support": BRANDS[DEFAULT_BRAND_HOST]["support"],
        },
        "helper_agent": dict(HELPER_AGENT),
        "products": company_products(),
        "policies": {
            "free_tier": (
                f"{FREE_DAILY['mesh']} sculpts and {FREE_DAILY['video']} videos "
                "per owner per day"
            ),
            "shipping": "1–3 business days production, 5–10 days worldwide",
            "personalisation": (
                "One pet photo becomes every product in the order — upload once"
            ),
            "watermark": "Free-tier videos are watermarked; paid tiers are not",
            "returns": f"Contact {BRANDS[DEFAULT_BRAND_HOST]['support']}",
            "payment": "Shopify checkout (card); XMR/Tor is research-only, not live",
        },
        "resources": {
            "shopify": {
                "store": os.environ.get("SHOPIFY_STORE", ""),
                "connected": bool(os.environ.get("SHOPIFY_STORE")),
                "role": "canonical product DB + checkout (GTM)",
            },
            "cloudflare": {
                "tunnel": True,
                "zones": sorted(BRANDS.keys()),
                "role": "edge, DNS, email routing, premesh transforms",
            },
            "storage": {"r2": True, "role": "private photos/meshes; public /img/ marketing only"},
            "mesh": {"provider": "Meshy", "live": bool(MESHY_API_KEY), "role": "photo-to-3D (only paid step)"},
            "mcp": {"port": 8799, "public": "https://mcp.oddhobb.com/mcp", "role": "agent surface"},
        },
        "capabilities": [
            {"name": "catalog.read", "kind": "read", "approval": "never",
             "note": "GET /api/catalog, /api/sections, /api/seo/products.json"},
            {"name": "seo.pack.read", "kind": "read", "approval": "never",
             "note": "8 AI attributes + Q&A for Google/Pinterest agents"},
            {"name": "companygraph.read", "kind": "read", "approval": "never",
             "note": "This graph — facts, policies, resources"},
            {"name": "mesh.sculpt", "kind": "write", "approval": "user_credits",
             "note": "Spends free daily sculpt credits; owner-sig or API key required"},
            {"name": "video.render", "kind": "write", "approval": "user_credits",
             "note": "Spends free video credits; watermarked on free tier"},
            {"name": "order.place", "kind": "write", "approval": "always",
             "note": "NOT IMPLEMENTED — products:order reserved for Shopify/Stripe"},
            {"name": "email.send", "kind": "write", "approval": "always",
             "note": "NOT IMPLEMENTED — capability reserved, no send path"},
        ],
    }


API_TOKEN = os.environ.get("API_TOKEN", "")


def ensure_dirs() -> None:
    for p in (DATA, LOCAL_TMP, LOCAL_MESH, UPLOAD_DIR, PRODUCTIMG_DIR):
        p.mkdir(parents=True, exist_ok=True)


# Public product renders for feeds and shopping agents (marketing assets only
# — user photos never land here). Served ungated at /img/ by the bridge.
PRODUCTIMG_DIR = DATA / "productimg"


def mint_token() -> str:
    return secrets.token_urlsafe(24)


# ── sections: the left rail, the shop chips, the subdomains ──────────────────
# Single source of truth (docs/navigation.md). `panel` = which tab a section
# opens; catalog sections additionally filter the shop grid. `host` = the
# subdomain that should deep-link straight into this section ("" = none yet).
SECTIONS: list[dict] = [
    {"id": "all",         "label": "All",         "icon": "🛍️", "panel": "shop",    "host": "", "blurb": "Everything we make, in one grid — every card already features your star."},
    {"id": "board-games", "label": "Board games", "icon": "🎲", "panel": "shop",    "host": "boardgames.oddhobb.com", "blurb": "Puzzles today, board games next — watch this shelf fill."},
    {"id": "gifts",       "label": "Gifts",       "icon": "🎁", "panel": "shop",    "host": "gifts.oddhobb.com", "blurb": "Figurines, prints, mugs — giftable things with your star on them."},
    {"id": "cards",       "label": "Cards",       "icon": "🎴", "panel": "shop",    "host": "cards.oddhobb.com", "blurb": "Printed and posted to the door — greeting cards and postcards."},
    {"id": "my",          "label": "My oddhobbs", "icon": "🐾", "panel": "upload",  "host": "my.oddhobb.com", "blurb": "Upload your people. We autosort them, you name them."},
]

# product id -> section. Anything absent lives in "All" only (the digital
# experiences: video/comedy/ar — deliberate until a Watch section exists).
SECTION_OF: dict[str, str] = {
    # cards
    "card": "cards", "greeting_card": "cards", "postcard": "cards",
    # board games
    "jigsaw": "board-games",
    # gifts (physical keepsakes + giftable digital)
    "figurine": "gifts", "bauble": "gifts", "sticker": "gifts",
    "framed_print": "gifts", "poster": "gifts", "photo_tile": "gifts",
    "cushion": "gifts", "mug": "gifts", "tote": "gifts",
    "notebook": "gifts", "canvas": "gifts", "wrapping_paper": "gifts",
}


# ── catalog metadata: one place for how a product PRESENTS itself ────────────
# Consumed by GET /api/catalog (site cards, MCP figg_catalog). Adding a
# product = PRODUCTS/PRODIGI entry + these two maps + SECTION_OF — nothing else.
PRODUCT_EMOJI: dict[str, str] = {
    "figurine": "\U0001f5ff", "bauble": "\U0001f384", "video": "\U0001f3ac",
    "comedy_show": "\U0001f3a4", "card": "\U0001f48c", "sticker": "\U0001f31f",
    "comedy_set": "\U0001f399\ufe0f", "ar_show": "\U0001f4f1",
}
PRODUCT_BLURB: dict[str, str] = {
    "figurine": "Your pet as a printed brick figure",
    "bauble": "Same sculpt, on the tree",
    "video": "A short clip, watermarked",
    "comedy_show": "A set at the comedy club",
    "card": "Printed and posted to the door",
    "sticker": "Peel, stick, repeat",
    "comedy_set": "Written for them, start to finish",
    "ar_show": "Scan it, watch them do the set",
}
# prodigi shapes -> emoji (blurb falls back to sku_note)
SHAPE_EMOJI: dict[str, str] = {
    "card": "\U0001f48c", "postcard": "\u2709\ufe0f", "sticker": "\U0001f31f",
    "print": "\U0001f5bc\ufe0f", "cushion": "\U0001f6cb\ufe0f", "mug": "\u2615",
    "tote": "\U0001f45c", "notebook": "\U0001f4d3", "jigsaw": "\U0001f9e9",
    "canvas": "\U0001f5bc\ufe0f",
}
