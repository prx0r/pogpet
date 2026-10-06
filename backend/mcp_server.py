"""figgsite MCP server — the platform, callable by an agent.

This is the "Muse agent drives everything" endgame in one file: ChatGPT, Grok,
Meta Muse or any MCP client connects, and gets the same verbs a human clicks.

    python3 -m backend.mcp_server     # stdio  (for local/agent harnesses)
    MCP_HTTP=1 python3 -m backend.mcp_server  # streamable HTTP on :8799/mcp

Identity: **bobdod** is the main helper agent (storefront + this MCP).
Tools act as whoever's key is in `FIGG_API_KEY` (put your own in .env), or
as the agent credential from `POST /api/agents`. The company graph
(`figg_companygraph`) is the canonical FACTS/RESOURCES/CAPABILITIES surface.

Every tool is a thin call to the HTTP API rather than direct DB access, so
the permission checks, credit accounting and validation are enforced in
exactly one place.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcp.server.mcpserver import MCPServer  # noqa: E402

API = os.environ.get("FIGG_API_BASE", "http://127.0.0.1:8798")
PORT = int(os.environ.get("MCP_PORT", "8799"))


def _service_token() -> str:
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("API_TOKEN="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("API_TOKEN", "")


def _key() -> str:
    return os.environ.get("FIGG_API_KEY", "")


mcp = MCPServer("figgsite", instructions=(
    "OddHobb storefront API (oddhobb.com): pets become meshes, meshes become products, "
    "meshes perform. Canonical funnel: ramble → figg_quick_map (confidence-ranked live "
    "lines) → upload photo → mesh → figg_fullchain_personalise_order(fulfil=true) → "
    "Shopify draft. Prices are EST until a Prodigi SKU is attached. Free tier: 3 sculpts "
    "and 5 videos per owner per day. Always show price before order. Never Meshy-spend "
    "without the human saying go. Controlled custom: registry coat/hat/pattern/line only."
))


async def _call(method: str, path: str, body: dict | None = None) -> dict:
    """Hit our own API with both the service token and the caller's key."""
    import urllib.request
    import urllib.error

    def work() -> dict:
        sep = "&" if "?" in path else "?"
        url = f"{API}{path}{sep}token={_service_token()}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        if data:
            req.add_header("Content-Type", "application/json")
        if _key():
            req.add_header("X-API-Key", _key())
        figg_owner = os.environ.get("FIGG_OWNER", "").strip()
        claimed = ""
        if body and isinstance(body, dict):
            claimed = str(body.get("owner") or "").strip()
        if not claimed:
            from urllib.parse import urlsplit,parse_qs
            claimed=str(parse_qs(urlsplit(path).query).get("owner",[""])[0]).strip()
        if figg_owner and claimed == figg_owner:
            from backend import config as _cfg
            req.add_header("X-Owner-Sig", _cfg.sign_owner(figg_owner))
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                return json.loads(raw)
            except Exception:
                return {"ok": False, "error": f"{e.code}: {raw[:200]}"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:300]}

    return await asyncio.get_event_loop().run_in_executor(None, work)


def _j(d: dict) -> str:
    return json.dumps(d, indent=1, default=str)


# ── identity ────────────────────────────────────────────────────────

async def figg_me() -> str:
    """Your profile: handle, active pog, roster and today's free credits."""
    return _j(await _call("GET", "/api/accounts/me"))


async def figg_create_account(handle: str, password: str = "",
                              display_name: str = "") -> str:
    """Create an account. `handle` becomes the owner of everything it makes.
    Returns an api_key shown once — store it."""
    return _j(await _call("POST", "/api/accounts",
                          {"handle": handle, "password": password,
                           "display_name": display_name}))


async def figg_login(handle: str, password: str) -> str:
    """Sign in with handle + password. Returns the api_key for this session."""
    return _j(await _call("POST", "/api/accounts/login",
                          {"handle": handle, "password": password}))


# ── meshes ──────────────────────────────────────────────────────────

async def figg_styles() -> str:
    """Ready-made characters to start from. No Meshy key required — a pet
    that looks like *yours* still needs photo-to-3D, but everything downstream
    of the mesh is free."""
    return _j(await _call("GET", "/api/styles"))


async def figg_install_style(style: str, owner: str = "") -> str:
    """Instantly install a style preset as an active pog (renders a portrait,
    stores it, binds all products). `style` is an id from figg_styles()."""
    return _j(await _call("POST", "/api/meshes/style",
                          {"style": style, "owner": owner}))


async def figg_mesh_status(mesh_id: str, owner: str = "") -> str:
    """Status of one mesh plus every product it is active in."""
    q = f"?owner={owner}" if owner else ""
    return _j(await _call("GET", f"/api/meshes/{mesh_id}{q}"))


async def figg_measure(mesh_id: str) -> str:
    """Geometry of a mesh: bounding box and print dimensions in mm."""
    return _j(await _call("GET", f"/api/meshes/{mesh_id}/measure"))


async def figg_print_export(mesh_id: str, format: str = "stl",
                             height_mm: float = 0) -> str:
    """Export a printable file. format is 'stl' or 'obj'; height_mm scales the
    model to that print height (0 = leave native size). Returns a URL."""
    return _j(await _call("GET",
                          f"/api/meshes/{mesh_id}/print?format={format}&height_mm={height_mm}"))


# ── shop ────────────────────────────────────────────────────────────

async def figg_products(owner: str = "", concept: str = "",
                        subject: str = "") -> str:
    """The Prodigi catalogue rendered against the owner's ACTIVE pog.
    `concept` is an id from figg_concepts(); `subject` is the name printed
    on the piece. Prices are LIVE when a SKU is attached, else EST."""
    q = f"?owner={owner}" if owner else ""
    if concept:
        q += ("&" if q else "?") + f"concept={concept}"
    if subject:
        q += ("&" if "?" in q else "?") + f"subject={subject}"
    return _j(await _call("GET", f"/api/products{q}"))


async def figg_concepts() -> str:
    """The 36-concept template library: wizard / mystic / christmas ×
    solo / couple / solo_pet / pet, each with art direction."""
    return _j(await _call("GET", "/api/concepts"))


async def figg_quote(sku: str, country: str = "GB", attrs: str = "{}") -> str:
    """Live Prodigi price for a SKU (item, shipping, tax, carrier)."""
    return _j(await _call("GET",
                          f"/api/prodigi/quote?sku={sku}&country={country}&attrs={attrs}"))


async def figg_check_sku(sku: str) -> str:
    """Does this Prodigi SKU exist, and what attributes does quoting need?"""
    return _j(await _call("GET", f"/api/prodigi/check?sku={sku}"))


# ── perform ─────────────────────────────────────────────────────────

async def figg_acts() -> str:
    """The talent-show roster (19 acts) and the three talents:
    comedy, dance, singing. Each act carries its own edge-tts voice."""
    return _j(await _call("GET", "/api/acts"))


async def figg_perform(talent: str, topic: str, mesh_id: str,
                       act: str = "", pet_name: str = "your pet",
                       voice: str = "ryan") -> str:
    """Write, voice and render a performance for a mesh. `talent` is
    comedy|dance|singing, `act` is an id from figg_acts(). ~45s, $0.
    Returns the video URL and the lines it performed."""
    d = await _call("POST", "/api/videos",
                    {"talent": talent, "topic": topic, "mesh_id": mesh_id,
                     "act": act, "pet_name": pet_name, "voice": voice,
                     "owner": os.environ.get("FIGG_OWNER", "")})
    try:
        vid = (d.get("video") or {}).get("id", "")
        if vid:
            d["watch_url"] = _watch_url(vid)
    except (AttributeError, TypeError):
        pass
    return _j(d)


async def figg_greeting(mesh_id: str, message: str, room: str = "void",
                        speaker_name: str = "", voice: str = "ryan",
                        owner: str = "") -> str:
    """Avatar greeting: the subject speaks your message verbatim in a room
    (void|club|podium|press|xmas). The video card — same quota as videos, $0.
    Returns the MP4 download. Keep messages under 600 chars."""
    return _j(await _call("POST", "/api/videos/greeting",
                         {"mesh_id": mesh_id, "message": message, "room": room,
                          "speaker_name": speaker_name, "voice": voice,
                          "owner": owner or os.environ.get("FIGG_OWNER", "")}))


async def figg_rooms(owner: str = "") -> str:
    """Greeting room registry: venues + which backdrops exist on disk."""
    return _j(await _call("GET", "/api/videos/rooms?owner=" + owner))


def _owner_or_env(owner: str) -> str:
    """Voice/room callers act for one shopper: explicit owner wins, otherwise
    the configured single-shopper identity. Never silently empty."""
    return owner or os.environ.get("FIGG_OWNER", "")


async def figg_guide_open(owner: str = "") -> str:
    """Open a personal-shopper session: ramble-first gifting, no search bar."""
    return _j(await _call("POST", "/api/guide/open", {"owner": _owner_or_env(owner)}))


async def figg_guide_turn(session_id: str, text: str, owner: str = "") -> str:
    """One shopper message: builds profile, refines packs, answers next step."""
    return _j(await _call("POST", "/api/guide/turn",
                         {"session_id": session_id, "text": text,
                          "owner": _owner_or_env(owner)}))


async def figg_guide_packs(session_id: str, owner: str = "") -> str:
    """Curated gift packs for the session: budget-filtered, motif-picked."""
    import urllib.parse
    q = urllib.parse.quote
    return _j(await _call("GET", f"/api/guide/packs?owner={q(_owner_or_env(owner))}&session_id={q(session_id)}"))


async def figg_credits(owner: str = "") -> str:
    """Today's free allowance: sculpts and videos remaining."""
    return _j(await _call("GET", f"/api/credits?owner={owner}"))


# ── foundation: catalog, flow, upload→mesh, and the tool manifest ────────────

async def figg_catalog() -> str:
    """Every product we make: id, label, price, section, emoji, blurb, preview kind."""
    return _j(await _call("GET", "/api/catalog"))


async def figg_flow(owner: str = "") -> str:
    """Upload->mesh->previews state in one call: stage (empty/uploaded/sculpting/ready), photos, meshes, active mesh."""
    return _j(await _call("GET", "/api/flow?owner=" + owner))


async def figg_start_mesh(photo_id: str, owner: str = "") -> str:
    """Start sculpting an uploaded photo (photo_id from figg_upload_photo) -> returns the mesh job.

    Pass `owner` when acting for a known handle — without FIGG_OWNER/API key
    matching that owner the backend refuses non-anon credit burns.
    """
    payload = {"photo_id": photo_id}
    if owner:
        payload["owner"] = owner
    return _j(await _call("POST", "/api/meshes", payload))


async def figg_upload_photo(file_name: str, owner: str = "") -> str:
    """Upload an image from the server sandbox (FIGG_UPLOAD_DIR) -> photo_id for figg_start_mesh."""
    import asyncio
    import urllib.error
    import urllib.request
    from pathlib import Path

    from backend import config

    base = Path(config.UPLOAD_DIR).resolve()
    src = Path(file_name)
    src = (src if src.is_absolute() else base / src).resolve()
    if not str(src).startswith(str(base)) or not src.is_file():
        return _j({"ok": False, "error": f"file must live inside the sandbox {base}"})

    def work() -> dict:
        boundary = "----fogg" + str(os.getpid())
        head = (f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="owner"\r\n\r\n{owner}\r\n'
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="photo"; filename="{src.name}"\r\n'
                f"Content-Type: application/octet-stream\r\n\r\n").encode()
        body = head + src.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        url = f"{API}/api/photos?token={_service_token()}"
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                return json.loads(raw)
            except Exception:
                return {"ok": False, "error": f"{e.code}: {raw[:200]}"}
        except Exception as e:                                  # noqa: BLE001
            return {"ok": False, "error": str(e)[:300]}

    return _j(await asyncio.get_event_loop().run_in_executor(None, work))


async def figg_companygraph() -> str:
    """OddHobb company graph — FACTS (products/policies), RESOURCES, CAPABILITIES, and the bobdod helper agent identity. Read-only."""
    return _j(await _call("GET", "/api/companygraph"))


async def figg_playbook() -> str:
    """Machine-readable funnel: ramble → confidence products → photo → mesh → checkout. Call this first when helping a customer shop."""
    return _j(await _call("GET", "/api/agent/playbook"))


async def figg_quick_map(text: str, owner: str = "") -> str:
    """Map a customer ramble/query onto live studio lines with confidence scores. Returns ranked matches + recommended coat/hat/pattern + next-step funnel."""
    return _j(await _call("POST", "/api/quick/map", {"text": text, "owner": owner}))


async def figg_product_assets(owner: str = "") -> str:
    """Studio product lines with stills, prices, assets (coats/hats/patterns) and the owner's active mesh id."""
    return _j(await _call("GET", "/api/products/studio?owner=" + (owner or "anon")))


async def figg_studio_props() -> str:
    """Prop registry: hats, coats, patterns, per-line allowed combos, custom policy."""
    return _j(await _call("GET", "/api/studio/props"))


async def figg_studio_retexture(line: str = "ornament", coat: str = "none",
                                hat: str = "none", pattern: str = "solid",
                                owner: str = "", mesh_id: str = "",
                                note: str = "") -> str:
    """Retexture preview: pick coat colour, optional santa/xmas hat, optional pattern.
    Returns stills for that combo + the full available registry. 0 Meshy credits.
    Registry ids only (e.g. coat=chocolate hat=santa pattern=spots). Coat is a preview grade."""
    return _j(await _call("POST", "/api/products/personalise", {
        "line": line, "coat": coat, "hat": hat, "pattern": pattern,
        "owner": owner, "mesh_id": mesh_id, "texture": note, "texture_note": note,
    }))


async def figg_studio_combos() -> str:
    """List pre-rendered coat / santa hat / pattern still sets + allowed line assets."""
    return _j(await _call("GET", "/api/studio/combos"))


async def figg_product_personalise(line: str, coat: str = "none", hat: str = "none",
                                    pattern: str = "solid", owner: str = "",
                                    mesh_id: str = "") -> str:
    """Validate controlled custom on a line → stills + price. Registry ids only."""
    return _j(await _call("POST", "/api/products/personalise", {
        "line": line, "coat": coat, "hat": hat, "pattern": pattern,
        "owner": owner, "mesh_id": mesh_id,
    }))


async def figg_checkout(line: str, coat: str = "none", hat: str = "none",
                        pattern: str = "solid", qty: int = 1,
                        amount_cents: int = 0, fulfil: bool = False,
                        owner: str = "", mesh_id: str = "", email: str = "",
                        note: str = "", remix_of: dict | None = None) -> str:
    """Reserve an order. fulfil=true also creates a Shopify draft (no card charge). Show price first.
    remix_of={designer, design} adds a flat $1 royalty to the original designer."""
    body = {
        "line": line, "coat": coat, "hat": hat, "pattern": pattern,
        "qty": qty, "fulfil": fulfil, "owner": owner, "mesh_id": mesh_id,
        "email": email, "note": note,
    }
    if remix_of:
        body["remix_of"] = remix_of
    if amount_cents:
        body["amount_cents"] = amount_cents
    return _j(await _call("POST", "/api/products/order", body))


async def figg_fullchain_personalise_order(line: str, coat: str = "none",
                                           pattern: str = "solid", hat: str = "none",
                                           qty: int = 1, amount_cents: int = 0,
                                           fulfil: bool = False, owner: str = "",
                                           mesh_id: str = "", email: str = "") -> str:
    """Personalise + order in one call for a studio line. Prefer this after figg_quick_map once the human confirms price."""
    body = {
        "line": line, "coat": coat, "pattern": pattern, "hat": hat,
        "qty": qty, "fulfil": fulfil, "owner": owner, "mesh_id": mesh_id,
        "email": email,
    }
    if amount_cents:
        body["amount_cents"] = amount_cents
    pers = await _call("POST", "/api/products/personalise", {
        "line": line, "coat": coat, "hat": hat, "pattern": pattern,
        "owner": owner, "mesh_id": mesh_id,
    })
    order = await _call("POST", "/api/products/order", body)
    return _j({"ok": bool((order or {}).get("ok")), "personalise": pers, "order": order})


async def figg_card_library(owner: str = "") -> str:
    """Photo library + card scenes. Photo cards need no mesh or Meshy spend."""
    import urllib.parse
    q = urllib.parse.quote(owner)
    return _j({"photos": await _call("GET", "/api/cards/photos?owner=" + q),
               "scenes": await _call("GET", "/api/cards/templates?owner=" + q),
               "designs": await _call("GET", "/api/cards/designs?owner=" + q)})


async def figg_card_save(spec: dict, owner: str = "", design_id: str = "",
                         expected_revision: int = 0) -> str:
    """Save a card scene: template, format, photos[{photo_id,crop,focus,cutout}], headline, recipient, sender, inside_message."""
    body = {"owner": owner, "spec": spec}
    if design_id:
        body.update(id=design_id, expected_revision=expected_revision)
    return _j(await _call("POST", "/api/cards/designs", body))


async def figg_card_render(design_id: str, revision: int, kind: str = "preview",
                           owner: str = "") -> str:
    """Render saved card preview/export/motion. Returns async job; same revision drives paper and MP4."""
    return _j(await _call("POST", f"/api/cards/{design_id}/render",
                         {"owner": owner, "revision": revision, "kind": kind}))


async def figg_card_scene(design_id: str, owner: str = "", revision: int = 0) -> str:
    """Get the shared card/video scene manifest and available output capabilities."""
    import urllib.parse
    path="/api/cards/"+urllib.parse.quote(design_id,safe="")+"/scene?owner="+urllib.parse.quote(owner)
    if revision:
        path+="&revision="+str(revision)
    return _j(await _call("GET",path))


async def figg_card_job(job_id: str, owner: str = "") -> str:
    """Check card render job status; ready results include owner-gated download URLs."""
    import urllib.parse
    return _j(await _call("GET", f"/api/cards/jobs/{job_id}?owner=" + urllib.parse.quote(owner)))


async def figg_card_cutout(photo_id: str, crop: list[float], owner: str = "") -> str:
    """Remove background after explicitly cropping the subject in a group photo. No face recognition or generative upscale."""
    return _j(await _call("POST", "/api/cards/cutouts", {"owner": owner, "photo_id": photo_id, "crop": crop}))


async def figg_card_reserve(design_id: str, revision: int, idempotency_key: str,
                            qty: int = 1, owner: str = "") -> str:
    """Reserve a real card with approved export and server price. Show price first. No payment or supplier fulfilment."""
    return _j(await _call("POST", f"/api/cards/{design_id}/order",
                         {"owner": owner, "revision": revision, "idempotency_key": idempotency_key, "qty": qty}))


async def figg_blueprints(owner: str = "") -> str:
    """Every product line with its design contract: locked interfaces, working
    envelope, material, colour cap, rough cost targets. The design space — a
    model designing for a line must keep every locked interface and stay
    inside the envelope. Designers add ?design=1 detail via figg_design_validate."""
    return _j(await _call("GET", "/api/products/studio?owner=" + (owner or "anon") + "&design=1"))


async def figg_design_validate(line: str, dims_mm: list[float] | None = None,
                               material: str = "", colors: int = 1,
                               text: str = "", volume_cm3: float | None = None) -> str:
    """Check a candidate design against a line's contract: envelope fit,
    material/colours, text length vs the zone, rough makr3d + printie cost.
    Geometry truth (manifold, interface dims) is verified at sample."""
    return _j(await _call("POST", "/api/design/validate", {
        "line": line, "dims_mm": dims_mm, "material": material,
        "colors": colors, "text": text, "volume_cm3": volume_cm3}))


async def figg_design_base(line: str) -> str:
    """The 3D base version to play with: master STL (reference lines) or the
    canonical dog GLB (mesh lines). Locked interfaces included as modelled."""
    return _j(await _call("GET", f"/api/design/base/{line}"))


async def figg_design_save(line: str, owner: str = "",
                           dims_mm: list[float] | None = None,
                           material: str = "", colors: int = 1,
                           text: str = "", volume_cm3: float | None = None) -> str:
    """Play with the base, save the design: validated spec stored as a draft.
    Returns design_id for figg_design_order. Invalid designs 400 with gaps."""
    return _j(await _call("POST", "/api/design/save", {
        "owner": owner, "line": line, "dims_mm": dims_mm, "material": material,
        "colors": colors, "text": text, "volume_cm3": volume_cm3}))


async def figg_design_order(design_id: str, owner: str = "", qty: int = 1,
                            fulfil: bool = False) -> str:
    """Order a saved design: re-validates, reserves, optional Shopify draft.
    Show price first. No card charge from this endpoint."""
    return _j(await _call("POST", "/api/design/order", {
        "design_id": design_id, "owner": owner, "qty": qty, "fulfil": fulfil}))


async def figg_blender_make(line: str, text: str, owner: str = "") -> str:
    """Use Blender on our farm box: emboss text onto the line's master via
    its adapter, get back a watertight STL URL. For remote agents (ChatGPT)
    with no local Blender — same contracts, headless, ~1-2 min."""
    return _j(await _call("POST", "/api/design/make",
                         {"owner": owner, "line": line, "text": text}))


async def figg_card_templates(owner: str = "") -> str:
    """Card templates with their paper design contracts: locked print truths
    (bleed, DPI, photo counts), envelope trims, stock, rough print costs."""
    return _j(await _call("GET", "/api/cards/templates?owner=" + (owner or "anon")))


async def figg_video_share(video_id: str) -> str:
    """One-click share link for a clip (?ref=). Prompt + script already live
    on the row, so shared sets replay. Signup with the ref installs free
    starter meshes — the viral funnel."""
    return _j(await _call("POST", f"/api/videos/{video_id}/share", {}))


async def figg_write_premise(topic: str, persona: str = "") -> str:
    """Sharpen a rough bit via pogtown's writing room. Feeds perform."""
    return _j(await _call("POST", "/api/jokes/premise",
                         {"topic": topic, "persona": persona}))


async def figg_write_riff(line: str) -> str:
    """Tags and alts for one line, from the writing room."""
    return _j(await _call("POST", "/api/jokes/riff", {"line": line}))


async def figg_gift_pack(budget_cents: int, owner: str = "",
                         line: str = "", mesh_id: str = "",
                         recipient: str = "") -> str:
    """Oddy's game: best gift inside a budget — physical + card + free video.
    Exact line honoured with cheap addons; otherwise best physical leaving
    room for a card. Show the total before ordering parts."""
    return _j(await _call("POST", "/api/gift-packs", {
        "budget_cents": budget_cents, "owner": owner, "line": line,
        "mesh_id": mesh_id, "recipient": recipient}))


async def figg_studio_orders(owner: str = "") -> str:
    """Your reservations and Shopify drafts. Read-only; nothing charges here."""
    return _j(await _call("GET", "/api/studio/orders?owner=" + (owner or "anon")))


async def figg_supplier_quote(line: str, material: str = "",
                              colors: int = 1) -> str:
    """Rough farm cost for a line at makr3d + printie. Estimates — live
    quotes win. Uses the line's contract dims and volume."""
    return _j(await _call("POST", "/api/design/validate", {
        "line": line, "material": material, "colors": colors}))


# ── the manifest: adding a tool = adding it to an area. One place. ───────────
async def figg_upload_chatgpt_file(file: dict, owner: str = "") -> str:
    """Pet photo attached in ChatGPT -> photo_id. ChatGPT populates `file`
    (download_url + file_id) at call time; the server fetches the bytes
    itself and runs them through intake. Never echo the URL."""
    import urllib.request
    import urllib.error
    url = (file or {}).get("download_url", "")
    name = (file or {}).get("file_name", "chatgpt-upload.jpg")
    if not url:
        return _j({"ok": False, "error": "no file attached — attach a photo in chat first"})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (oddhobb-mcp)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            blob = r.read(12 * 1024 * 1024 + 1)
        if len(blob) > 12 * 1024 * 1024:
            return _j({"ok": False, "error": "photo too large (12MB max)"})
    except Exception as e:  # noqa: BLE001
        return _j({"ok": False, "error": f"could not fetch attached photo: {str(e)[:120]}"})
    import uuid as _uuid
    import mimetypes as _mt
    boundary = "oddhobb" + _uuid.uuid4().hex
    ctype, _ = _mt.guess_type(name)
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"owner\"\r\n\r\n{(owner or 'anon')}\r\n",
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{name}\"\r\n"
        f"Content-Type: {ctype or 'image/jpeg'}\r\n\r\n",
    ]
    body = parts[0].encode() + parts[1].encode() + blob + f"\r\n--{boundary}--\r\n".encode()
    sep = "&"
    target = f"{API}/api/photos?token={_service_token()}"
    req = urllib.request.Request(target, data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        return e.read().decode()
    except Exception as e:  # noqa: BLE001
        return _j({"ok": False, "error": str(e)[:200]})


async def figg_preview_image(line: str = "ornament", owner: str = "") -> list:
    """Product preview as an actual image in chat, not a URL. Returns the
    line's hero still inline + price text."""
    from mcp.types import ImageContent, TextContent
    try:
        d = await _call("GET", "/api/products/studio?owner=" + (owner or "anon"))
        item = next((i for i in d.get("items", []) if i.get("id") == line), None)
        if not item:
            return [TextContent(type="text", text=f"unknown line {line}")]
        hero = ((item.get("stills") or {}).get("hero") or "")
        price = f"£{(item.get('price_cents') or 0) / 100:.2f}"
        import urllib.request
        if not hero.startswith("http"):
            hero = "https://oddhobb.com" + hero
        req = urllib.request.Request(hero, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            blob, mime = r.read(2 * 1024 * 1024), r.headers.get("Content-Type", "image/png")
        import base64
        return [TextContent(type="text", text=f"{item.get('label', line)} — {price}"),
                ImageContent(type="image", data=base64.b64encode(blob).decode(),
                             mimeType=mime.split(";")[0])]
    except Exception as e:  # noqa: BLE001
        from mcp.types import TextContent
        return [TextContent(type="text", text=f"preview failed: {str(e)[:150]}")]


# ── inline video widget (MCP Apps UI) ────────────────────────────────
# Plain tool results can't play video in chat — no video content type.
# This widget does: ChatGPT renders it in an iframe, it grabs the first
# playable URL from the tool result and plays it.
VIDEO_PLAYER_URI = "ui://oddhobb/video-player"

VIDEO_PLAYER_HTML = """<!doctype html><html><body style="margin:0;background:#111">
<video id="v" controls playsinline style="width:100%;max-height:80vh;background:#000"></video>
<p id="m" style="color:#ccc;font:13px sans-serif;padding:8px">Waiting for the clip…</p>
<script>
var src = null;
function pick(text) {
  if (!text) return null;
  var m = String(text).match(/https?:\\/\\/[^\\s"']+\\.mp4[^\\s"']*|https?:\\/\\/[^\\s"']+\\/file[^\\s"']*/);
  return m ? m[0] : null;
}
function render(text) {
  var u = pick(text);
  var v = document.getElementById("v"), m = document.getElementById("m");
  if (u && u !== src) { src = u; v.src = u; m.textContent = ""; }
  else if (!u) { m.textContent = "No playable clip in this result yet."; }
}
window.addEventListener("message", function (event) {
  if (event.source !== window.parent) return;
  var msg = event.data || {};
  if (msg.method === "ui/notifications/tool-result" && msg.params) {
    var p = msg.params;
    var text = (p.structuredContent && JSON.stringify(p.structuredContent)) || "";
    (p.content || []).forEach(function (c) { if (c.text) text += "\\n" + c.text; });
    render(text);
  }
});
setTimeout(function () {
  if (!src) render((window.openai && window.openai.toolOutput) || "");
}, 1500);
</script></body></html>"""


@mcp.resource(VIDEO_PLAYER_URI, mime_type="text/html;profile=mcp-app")
async def oddhobb_video_player() -> str:
    """Inline video player for perform clips and shared videos."""
    return VIDEO_PLAYER_HTML


def _watch_url(vid: str) -> str:
    tok = (ROOT / ".token").read_text().strip() if (ROOT / ".token").exists() else os.environ.get("BRIDGE_TOKEN", "")
    base = f"https://oddhobb.com/backend/api/videos/{vid}/file"
    return base + (f"?token={tok}" if tok else "")


# _meta per tool: ChatGPT file picker wiring. figg_upload_chatgpt_file
# declares its `file` param so ChatGPT attaches the photo at call time.
TOOL_META: dict[str, dict] = {
    "figg_upload_chatgpt_file": {
        "openai/fileParams": ["file"],
    },
    "figg_perform": {
        "ui": {"resourceUri": VIDEO_PLAYER_URI},
        "openai/outputTemplate": VIDEO_PLAYER_URI,
    },
    "figg_video_share": {
        "ui": {"resourceUri": VIDEO_PLAYER_URI},
        "openai/outputTemplate": VIDEO_PLAYER_URI,
    },
}


TOOL_AREAS: dict[str, list] = {
    "cards":     [figg_card_library, figg_card_save, figg_card_render,
                  figg_card_job, figg_card_scene, figg_card_cutout, figg_card_reserve,
                  figg_card_templates],
    "design":    [figg_blueprints, figg_design_validate, figg_design_base,
                  figg_design_save, figg_design_order, figg_blender_make],
    "flow":      [figg_flow, figg_upload_photo, figg_upload_chatgpt_file,
                  figg_preview_image, figg_start_mesh, figg_playbook, figg_quick_map,
                  figg_guide_open, figg_guide_turn, figg_guide_packs],
    "identity":  [figg_me, figg_create_account, figg_login, figg_credits],
    "mesh":      [figg_mesh_status, figg_measure, figg_print_export],
    "shop":      [figg_catalog, figg_products, figg_concepts, figg_quote,
                  figg_check_sku, figg_product_assets, figg_studio_props,
                  figg_studio_combos, figg_studio_retexture,
                  figg_product_personalise, figg_checkout,
                  figg_fullchain_personalise_order, figg_gift_pack,
                  figg_studio_orders, figg_supplier_quote],
    "style":     [figg_styles, figg_install_style],
    "stage":     [figg_acts, figg_perform, figg_greeting, figg_rooms,
                  figg_video_share, figg_write_premise, figg_write_riff],
    "company":   [figg_companygraph],
}


async def figg_tools() -> str:
    """The self-describing library: every area and tool this MCP server exposes."""
    areas = {a: [{"name": fn.__name__,
                   "doc": (fn.__doc__ or "").strip().split("\n")[0]}
                  for fn in fns]
             for a, fns in TOOL_AREAS.items()}
    count = sum(len(v) for v in TOOL_AREAS.values()) + 1   # + figg_tools itself
    return _j({"ok": True, "count": count, "areas": areas})


for _fns in list(TOOL_AREAS.values()):
    for _fn in _fns:
        mcp.tool(meta=TOOL_META.get(_fn.__name__))(_fn)
mcp.tool()(figg_tools)


async def main() -> None:
    if os.environ.get("MCP_HTTP"):
        print(f"fogg MCP (streamable http) on http://127.0.0.1:{PORT}/mcp", file=sys.stderr)
        # Local only: the bridge proxies /mcp with a token gate. Never
        # expose this directly — its tools call the API with the service token.
        await mcp.run_streamable_http_async(host="127.0.0.1", port=PORT)
    else:
        await mcp.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
