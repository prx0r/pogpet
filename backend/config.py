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
    return "owner-sig:" + (API_TOKEN or secrets.token_hex(16))


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
    return BRANDS[DEFAULT_BRAND_HOST]["domain"]

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
# Lines are SKUs of the SAME canonical mesh — scale + hardware only.
STUDIO_LINES: dict[str, dict] = {
    "ornament": {
        "label": "Xmas ornament",
        "product": "bauble",
        "scale_mm": 80,
        "hardware": "printed loop",
        "blurb": "Tree hanger. Loop is part of the print.",
        "status": "live",
        "price_cents": 1299,
        # props that make sense on THIS line (Products tab + MCP)
        "assets": {
            "hats": ["none", "santa"],
            "coats": ["none", "cream", "golden", "chocolate", "black", "fawn", "grey"],
        },
        "theme": "xmas",
    },
    "keychain": {
        "label": "Keychain",
        "product": "figurine",
        "scale_mm": 60,
        "hardware": "printed loop",
        "blurb": "Same design, smaller. No metal.",
        "status": "live",
        "price_cents": 1499,
        "assets": {
            "hats": ["none"],
            "coats": ["none", "cream", "golden", "chocolate", "black", "fawn", "grey"],
        },
        "theme": "everyday",
    },
    "brick": {
        "label": "Brick figure",
        "product": "figurine",
        "scale_mm": 75,
        "hardware": "none",
        "blurb": "Desk figure — modular props when the brick mesh lands.",
        "status": "soon",
        "price_cents": 1999,
        "assets": {"hats": ["none"], "coats": ["none"]},
        "theme": "desk",
    },
}

# Coat = material grade on the existing texture (previews). Production
# multi-colour is a live farm quote — never pretend a grade is a print SKU.
STUDIO_COATS: list[dict] = [
    {"id": "none",     "label": "As printed", "hex": ""},
    {"id": "cream",    "label": "Cream",      "hex": "#EADBBE"},
    {"id": "golden",   "label": "Golden",     "hex": "#E6B86B"},
    {"id": "chocolate","label": "Chocolate",  "hex": "#6B4229"},
    {"id": "black",    "label": "Black",      "hex": "#1F1F1F"},
    {"id": "fawn",     "label": "Fawn",       "hex": "#D1AD85"},
    {"id": "grey",     "label": "Grey",       "hex": "#8C8C8F"},
]

# Hats = free Blender props seated on the measured skull.
STUDIO_HATS: list[dict] = [
    {"id": "none",  "label": "None",     "asset": "", "status": "live"},
    {"id": "santa", "label": "Santa hat","asset": "data/assets/hats/oga-santa/santa_hat.fbx",
     "status": "live", "licence": "CC0", "lines": ["ornament"]},
]

# Canonical product GLB (loop amend) served from /img/prod/ — demo + fallback
STUDIO_CANONICAL_GLB = "/img/prod/chibi-figure-hook.glb"
STUDIO_STILL_DIR = "prod"  # data/productimg/prod → /img/prod/
# Calling-card portrait under the character select (exact product still)
STUDIO_CALLING_CARD = "/img/prod/prod-hero.png"

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
# oddhobb.com, ochema.co (and pog.pet legacy) all serve this same app.
# Brand strings NEVER live in frontend text: GET /api/brand answers per
# request Host, and premesh zones follow the request host so Cloudflare
# pulls transformation sources from the zone actually serving them.
BRANDS = {
    "oddhobb.com": {"brand": "oddhobb",
                    "tagline": "what odd thing shall we make you?",
                    "support": "support@oddhobb.com"},
    "ochema.co":   {"brand": "ochema",
                    "tagline": "what odd thing shall we make you?",
                    "support": "support@ochema.co"},
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
