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
MCP_VERSION = "1.12.0"


def _service_token() -> str:
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("API_TOKEN="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("API_TOKEN", "")


def _key() -> str:
    return os.environ.get("FIGG_API_KEY", "")


mcp = MCPServer("oddhobb", instructions=(
    "OddHobb storefront API (oddhobb.com): pets become meshes, meshes become products, "
    "meshes perform. Canonical funnel: ramble → figg_quick_map (confidence-ranked live "
    "lines) → upload photo → mesh → figg_fullchain_personalise_order(fulfil=true) → "
    "Shopify draft. Prices are EST until a Prodigi SKU is attached. Free tier: 3 sculpts "
    "and 5 videos per owner per day. Always show price before order. Never Meshy-spend "
    "without the human saying go. Controlled custom: registry coat/hat/pattern/line only."
))


async def _call(method: str, path: str, body: dict | None = None,
                api_key: str = "", owner_sig: str = "") -> dict:
    """Hit our own API with both the service token and the caller's key.
    api_key (a user's own key, e.g. fresh from Google sign-in) travels as
    X-API-Key so writes land under THEIR account, never the operator's."""
    import urllib.request
    import urllib.error

    def work() -> dict:
        sep = "&" if "?" in path else "?"
        url = f"{API}{path}{sep}token={_service_token()}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        if data:
            req.add_header("Content-Type", "application/json")
        # Transport stamp: Flask trusts X-MCP only with the service token
        # (direct 127.0.0.1 call, never via the bridge — the bridge strips
        # X-MCP, so REST/browser cannot spoof via=mcp).
        req.add_header("X-MCP", "1")
        caller = (api_key or "").strip() or _key()
        if caller:
            req.add_header("X-API-Key", caller)
        if (owner_sig or "").strip():
            req.add_header("X-Owner-Sig", owner_sig.strip())
        figg_owner = os.environ.get("FIGG_OWNER", "").strip()
        owners = {figg_owner} | {o.strip() for o in
                                 os.environ.get("FIGG_OWNERS", "").split(",")}
        owners.discard("")
        claimed = ""
        if body and isinstance(body, dict):
            claimed = str(body.get("owner") or "").strip()
        if not claimed:
            from urllib.parse import urlsplit,parse_qs
            claimed=str(parse_qs(urlsplit(path).query).get("owner",[""])[0]).strip()
        if claimed in owners:
            from backend import config as _cfg
            req.add_header("X-Owner-Sig", _cfg.sign_owner(claimed))
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                d = json.loads(raw)
                if isinstance(d, dict):
                    d.setdefault("http_status", e.code)
                    return d
                return {"ok": False, "error": str(d)[:200], "http_status": e.code}
            except Exception:
                return {"ok": False, "error": f"{e.code}: {raw[:200]}", "http_status": e.code}
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


async def figg_mint_agent(api_key: str, name: str, permissions: list | None = None) -> str:
    """Mint a delegated agent credential under YOUR account (api_key from sign-in
    or Google session). Returns agent_api_key (shown once) — paste THAT into
    ChatGPT/Hark/Muse, never the bridge token. Own handle, your wallet,
    revocable any time via figg_revoke_agent. Full tier only."""
    return _j(await _call("POST", "/api/agents",
                         {"name": name, "permissions": permissions or []},
                         api_key=api_key))


async def figg_my_agents(api_key: str) -> str:
    """List your delegated agents + available permissions. Full tier only."""
    return _j(await _call("GET", "/api/agents", api_key=api_key))


async def figg_revoke_agent(api_key: str, agent_id: str) -> str:
    """Kill an agent credential instantly. Nothing else changes. Full tier only."""
    return _j(await _call("POST", f"/api/agents/{agent_id}/revoke", {}, api_key=api_key))


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


async def figg_start_mesh(photo_id: str, owner: str = "",
                            single: bool | None = None) -> str:
    """Start sculpting an uploaded photo (photo_id from figg_upload_photo) -> returns the mesh job.

    Pass `owner` when acting for a known handle — without FIGG_OWNER/API key
    matching that owner the backend refuses non-anon credit burns.
    single=None (default): one photo sculpts single-view; 3 angles of the
    same subject auto-upgrade to a multi-image build (same 1 credit).
    single=True forces single-view; single=False demands 3 angles.
    Funding order: genesis (first mesh free, once per owner) → credit
    balance → daily. Provider failures refund the exact funding source, once.
    """
    payload = {"photo_id": photo_id}
    if single is not None:
        payload["single"] = single
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


async def figg_creative_templates(api_key: str='') -> str:
    """Versioned executable card/scene templates: taxonomy, typed slots and renderers."""
    return _j(await _call('GET', '/api/creative/templates', api_key=api_key))


async def figg_creative_catalog(style: str='', occasion: str='', audience: str='', tone: str='', q: str='', api_key: str='') -> str:
    """Browse the same viral-format library customers see on oddhobb.com.
    Filter by occasion, recipient, tone/style, or free-text meme intent."""
    import urllib.parse
    params = {'style': style, 'occasion': occasion, 'audience': audience, 'tone': tone, 'q': q}
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v})
    return _j(await _call('GET', '/api/creative/catalog' + ('?' + qs if qs else ''), api_key=api_key))


async def figg_creative_brief(subject_id: str='', name: str='', owner: str='', occasion: str='general', tone: str='funny', budget_cents: int=0, request: str='', api_key: str='') -> str:
    """Compile the creative brief from the person graph: occasion + recipient
    facts + available assets + ask. Goes to the matcher, never a renderer."""
    return _j(await _call('POST', '/api/creative/brief', {'subject_id': subject_id, 'name': name, 'owner': owner, 'occasion': occasion, 'tone': tone, 'budget_cents': budget_cents, 'request': request}, api_key=api_key))


async def figg_creative_match(brief: dict | None=None, limit: int=5, api_key: str='') -> str:
    """Deterministic template ranking: eligibility filter + weighted score +
    reasons. Pass the brief from figg_creative_brief. Refuses error-shaped or
    occasion-less briefs instead of ranking garbage."""
    b = dict(brief or {})
    if isinstance(b.get('brief'), dict):
        b = dict(b['brief'])
    if b.get('ok') is False or not b.get('occasion'):
        return _j({'ok': False, 'error': 'brief failed or has no occasion — fix figg_creative_brief first (it returns the error), never match on it'})
    return _j(await _call('POST', '/api/creative/match', {'brief': b, 'limit': limit}, api_key=api_key))


async def figg_creative_revision(project_id: str='', template_id: str='', owner: str='', subject_id: str='', fields: dict | None=None, subjects: list | None=None, brief: dict | None=None, api_key: str='') -> str:
    """Fill template fields and freeze an immutable revision. Copy QC enforced
    (overflow/missing); geometry stays in the template. Edits = new revisions.
    Subject slots live in fields by slot id (fields.star = subject_id) — the
    top-level subjects list does not fill slots."""
    return _j(await _call('POST', '/api/creative/revisions', {'project_id': project_id, 'template_id': template_id, 'owner': owner, 'subject_id': subject_id, 'fields': fields or {}, 'subjects': subjects or [], 'brief': brief or {}}, api_key=api_key))


# ── six high-level agent tools: the whole product behind six names ─────
# Muse/ChatGPT never name providers; each fans out to figg_* machinery.

async def oddhobb_people(owner: str = "", api_key: str = "") -> str:
    """Whose world is this: subjects + profile facts for an owner. Pass your own api_key (from figg_create_account/figg_login) to act as you — otherwise reads land as anon."""
    return _j(await _call("GET", "/api/oddhobb/people?owner=" + (owner or "anon"), api_key=api_key))


async def oddhobb_families(owner: str = "", api_key: str = "", owner_sig: str = "") -> str:
    """Family groups with members, roles, face-emblem covers (people + pets). Image-first roster; names optional."""
    return _j(await _call("GET", "/api/studio/families?owner=" + owner, api_key=api_key, owner_sig=owner_sig))


async def oddhobb_reminders(owner: str = "", within_days: int = 30, api_key: str = "", owner_sig: str = "") -> str:
    """Birthday countdowns: who, days until, gift lines, funny-card templates, staged email draft. Birthdays are PII — owner-enforced."""
    return _j(await _call("GET", f"/api/family/reminders?owner={owner}&within_days={within_days}", api_key=api_key, owner_sig=owner_sig))


async def oddhobb_candidates(line: str, kind: str = "prodigi", n: int = 8, owner: str = "", api_key: str = "", owner_sig: str = "") -> str:
    """Ranked face shortlist behind one product line's tags — best first, arrows cycle the rest. Powers the site carousel and provider fills."""
    return _j(await _call("GET", f"/api/products/candidates?owner={owner}&kind={kind}&line={line}&n={n}", api_key=api_key, owner_sig=owner_sig))


async def oddhobb_fill_template(template_id: str, subjects: list | None = None, owner: str = "", api_key: str = "", owner_sig: str = "") -> str:
    """Fill a layout template (wrap_solo/trio_card/photo_card) from labelled photos: distinct picks, min_px print truth, per-provider payloads (Gelato/Printify staged, Prodigi renderable)."""
    qs = f"/api/templates/fill?owner={owner}&template_id={template_id}"
    if subjects:
        from urllib.parse import quote as _q
        qs += "&subjects=" + _q(",".join(subjects))
    return _j(await _call("GET", qs, api_key=api_key, owner_sig=owner_sig))


async def oddhobb_quotes(line: str = "wrapping_paper", country: str = "GB") -> str:
    """Speed vs value across suppliers for one product line: grades, cost breakdowns, picks."""
    return _j(await _call("GET", f"/api/quotes/compare?line={line}&country={country}"))


async def oddhobb_project_check(idea: dict | None = None) -> str:
    """Paste a kit idea, get the manufacturing truth: per-lane verdicts across 3D/paper/AliExpress/kitting, known costs, staged unknowns. Verdict: producible / staged / blocked."""
    return _j(await _call("POST", "/api/projects/check", {"idea": idea or {}}))


async def oddhobb_recipe_check(recipe: str, warehouse: str = "Shenzhen", qty: int = 1) -> str:
    """Can this warehouse build N boxes today? Per-component stock status + box quote from published base rates."""
    return _j(await _call("GET", f"/api/recipes/check?recipe={recipe}&warehouse={warehouse}&qty={qty}"))


async def oddhobb_gift_compile(recipe: str, warehouse: str = "Shenzhen", ship_cents: int | None = None) -> str:
    """Compile a gift recipe: resolve registry + product lines, apply the postage rule, feasibility score. Ship unknown → viability pending the parcel quote."""
    body: dict = {"recipe": recipe, "warehouse": warehouse}
    if ship_cents is not None:
        body["ship_cents"] = ship_cents
    return _j(await _call("POST", "/api/gifts/compile", body))


async def oddhobb_track_order(order_id: str, owner: str = "", api_key: str = "", owner_sig: str = "") -> str:
    """Track one order by id: status, lines, price, checkout links. Owner-enforced."""
    return _j(await _call("GET", f"/api/orders/track?owner={owner}&order_id={order_id}", api_key=api_key, owner_sig=owner_sig))


async def oddhobb_object_get(object_id: str) -> str:
    """Resolve an agent-addressable object (QR scan): digital asset, capabilities, live event state. Public, no PII."""
    return _j(await _call("GET", f"/api/objects/{object_id}/resolve"))


async def oddhobb_object_state(object_id: str, event: str, owner: str = "", api_key: str = "", owner_sig: str = "") -> str:
    """Record an agent event on an owned object (working/needs_approval/finished_artwork/visitor/offline/new_message/idle). Owner-enforced."""
    return _j(await _call("POST", f"/api/objects/{object_id}/state", {"owner": owner, "event": event}, api_key=api_key, owner_sig=owner_sig))


async def oddhobb_ideas(person: str='', occasion: str='general', request: str='', owner: str='', subject_id: str='', context: list | None=None, tone: str='funny', budget_cents: int=0, api_key: str='', owner_sig: str='') -> str:
    """Person + occasion + request (+ your relevant agent_memory context facts)
    → ranked creative ideas with reasons. Send facts, never whole memories."""
    return _j(await _call('POST', '/api/oddhobb/ideas', {'person': person, 'occasion': occasion, 'request': request, 'owner': owner, 'subject_id': subject_id, 'context': context or [], 'tone': tone, 'budget_cents': budget_cents}, api_key=api_key, owner_sig=owner_sig))


async def oddhobb_create(idea_id: str='', owner: str='', subject_id: str='', person: str='', overrides: dict | None=None, brief: dict | None=None, api_key: str='', owner_sig: str='') -> str:
    """Idea → frozen creative revision. Fifteen ops, one call."""
    return _j(await _call('POST', '/api/oddhobb/create', {'idea_id': idea_id, 'owner': owner, 'subject_id': subject_id, 'person': person, 'overrides': overrides or {}, 'brief': brief or {}}, api_key=api_key, owner_sig=owner_sig))


async def oddhobb_render(creative_id: str='', revision: int=1, owner: str='', outputs: list | None=None, policy: str='free', routes: dict | None=None, api_key: str='') -> str:
    """Realize a revision: preview now (free); photoreal/video/lipsync route
    through the vault on use-mine/best/specific, staged with reasons otherwise."""
    return _j(await _call('POST', '/api/oddhobb/render', {'creative_id': creative_id, 'revision': revision, 'owner': owner, 'outputs': outputs or ['preview'], 'policy': policy, 'routes': routes or {}}, api_key=api_key))


async def oddhobb_status(creative_id: str='', api_key: str='') -> str:
    """Creative status: latest revision + artifacts with QC state."""
    return _j(await _call('GET', f'/api/oddhobb/status/{creative_id}', api_key=api_key))


async def oddhobb_buy(creative_id: str='', design_id: str = "", revision: int=1,
                      owner: str='', product: str='greeting_card', qty: int=1,
                      idempotency_key: str = "", api_key: str = "",
                      owner_sig: str = "", ctx=None) -> list:
    """Buy this exact finished thing. Card path (design_id): pins the
    revision, requires a signer, returns a Shopify checkout URL — money
    moves only at Shopify, never here. Creative path (creative_id):
    reserves a QC-passed revision, no charge."""
    from mcp.types import TextContent
    who = _resolve_owner(owner, api_key, ctx)
    key_arg = api_key or _bearer_key(ctx)
    if design_id:
        cur = await _call("GET", "/api/cards/designs/" + design_id +
                          "?owner=" + who, api_key=key_arg, owner_sig=owner_sig)
        if not cur.get("ok"):
            return [TextContent(type="text", text=_j(cur))]
        spec = ((cur.get("design") or {}).get("spec")) or {}
        rev = int(revision or (cur.get("design") or {}).get("revision", 1))
        if not str(spec.get("sender") or "").strip():
            nm = str(spec.get("recipient") or "them")
            return [TextContent(type="text", text=_j(_env(
                status="needs_input",
                summary=f"Who signs the card for {nm}?",
                requires_action={"type": "signature", "design_id": design_id,
                                 "message": "Tell me who signs, then say buy again."},
                next_actions=[])))]
        qty_n = max(1, min(int(qty or 1), 20))
        out = await _call("POST", f"/api/cards/{design_id}/checkout",
                          {"owner": who, "revision": rev, "qty": qty_n,
                           "idempotency_key": idempotency_key or f"buy-{design_id}-r{rev}-q{qty_n}"},
                          api_key=key_arg, owner_sig=owner_sig)
        if not out.get("ok"):
            return [TextContent(type="text", text=_j(out))]
        try:
            from backend import cards as _cardsmod
            _canon = _cardsmod.card_price().get("price_cents", 299)
        except Exception:
            _canon = 299
        cents = ((out.get("product") or {}).get("price_cents")
                 or (out.get("order") or {}).get("price_cents") or _canon) * 1
        label = ((out.get("product") or {}).get("name")
                 or "Personalised 5×7 Greeting Card")
        return [TextContent(type="text", text=_j(_env(
            status="checkout_ready", id=design_id, summary=f"{label} — pay to print.",
            price_cents=cents, next_actions=[],
            extra={"design_id": design_id, "revision": rev,
                   "checkout_url": out.get("checkout_url", ""),
                   "product_url": out.get("product_url", out.get("card_url", "")),
                   "product": label})))]
    if not creative_id:
        return [TextContent(type="text", text=_j(
            {"ok": False, "error": "pass design_id (card) or creative_id"}))]
    out = await _call('POST', '/api/oddhobb/buy', {'creative_id': creative_id, 'revision': revision, 'owner': who, 'product': product, 'qty': qty}, api_key=key_arg)
    return [TextContent(type="text", text=_j(out))]


async def oddhobb_providers(owner: str='', api_key: str='') -> str:
    """Which creative providers are on for this owner: {free: true, fal: …}.
    Secrets are never visible — capabilities only. Policies: free/use-mine/best/specific."""
    return _j(await _call('GET', '/api/providers?owner=' + (owner or 'anon'), api_key=api_key))


async def oddhobb_capsule(subject_id: str='', owner: str='', api_key: str='') -> str:
    """Person Capsule: identity/voice/behaviour/spatial/knowledge/provenance
    for a subject. Input to every template."""
    return _j(await _call('GET', f'/api/capsule/{subject_id}?owner=' + (owner or 'anon'), api_key=api_key))


async def oddhobb_capsule(subject_id: str='', owner: str='', api_key: str='') -> str:
    """Person Capsule: identity/voice/behaviour/spatial/knowledge/provenance
    for a subject. Input to every template."""
    return _j(await _call('GET', f'/api/capsule/{subject_id}?owner=' + (owner or 'anon'), api_key=api_key))


async def oddhobb_make_card(subject_id: str = "", occasion: str = "birthday",
                            vibe: str = "playful_balloons", tone: str = "funny",
                            message_hint: str = "", signature: str = "",
                            owner: str = "", api_key: str = "",
                            owner_sig: str = "", template: str = "birthday_4photo",
                            front_art_url: str = "", inside_art_url: str = "") -> list:
    """Make a birthday card in ONE call. Canonical (birthday_4photo): resolves
    the 4 best SOLO photos, writes bounded copy, saves revision 1, renders
    views + print PDF. Fullbleed (birthday_fullbleed): needs front_art_url —
    without it returns art_required (409, never a silent collage); with it,
    attaches art + copy in the same call. Relationship label (Dad) for live
    headlines, never the full name."""
    from mcp.types import TextContent
    from backend import cards as _cards
    if not signature.strip():
        return [TextContent(type="text", text=_j({"ok": False, "error": "signature required — ask the human who signs the card (never default to the recipient)"}))]
    if (template or "") == "birthday_fullbleed" and not (front_art_url or "").strip():
        return [TextContent(type="text", text=_j({"ok": False, "http_status": 409,
                             "error": "art_required — fullbleed needs front art: call oddhobb_attach_card_art "
                                      "(or pass front_art_url here); never fall back to a collage silently",
                             "template": "birthday_fullbleed"}))]
    people = await _call("GET", "/api/oddhobb/people?owner=" + (owner or "anon"),
                         api_key=api_key, owner_sig=owner_sig)
    sub = _find_subject(people, "", subject_id)
    if not sub:
        return [TextContent(type="text", text=_j({"ok": False, "error": "unknown subject — check oddhobb_people first"}))]
    if (template or "") == "birthday_fullbleed":
        # fullbleed branch: copy + attached art, one call. Relationship label
        # on live text (Dad), never the subject's full name.
        label = _cards.display_label(sub.get("name", ""), sub.get("relationship", ""))
        prof = {"name": label, "relationship": sub.get("relationship", ""),
                "interests": sub.get("interests", []), "memories": sub.get("memories", [])}
        lines = _cards.message_lines(prof, tone)
        message = (message_hint.strip()[:240] if message_hint.strip()
                   else (lines[0]["text"][:240] if lines else ""))
        title = f"Happy Birthday, {label}!"[:40]
        return await oddhobb_attach_card_art(
            front_art_url=front_art_url, inside_art_url=inside_art_url,
            headline=title, recipient=label, sender=signature.strip()[:40],
            inside_message=message, headline_baked=True, art_source="make_card",
            prompt="", owner=owner, api_key=api_key, owner_sig=owner_sig)
    prof = {"name": sub.get("name", ""), "relationship": sub.get("relationship", ""),
            "interests": sub.get("interests", []), "memories": sub.get("memories", [])}
    pids: list[str] = []
    try:
        from backend import subject_assets as _sa
        res = _sa.resolve(sub.get("id", ""), owner or "anon")
        ranked = sorted((res.get("body_candidates") or []) + (res.get("face_candidates") or []),
                        key=lambda c: float(c.get("quality", c.get("face_quality", 0))), reverse=True)
        seen: set[str] = set()
        for c in ranked:
            aid = str(c.get("asset_id") or "")
            if aid and aid not in seen:
                seen.add(aid)
                pids.append(aid)
        # solo portraits first: group photos confuse single-recipient cards
        pids = _cards.solo_first(owner or "anon", pids)[:4]
    except Exception:  # noqa: BLE001
        pids = []
    if len(pids) < 4:
        return [TextContent(type="text", text=_j({"ok": False, "error": f"need 4 photos — only {len(pids)} confirmed"}) )]
    name = sub.get("name") or "them"
    short = str(name).split()[0] if str(name).split() else name
    title = f"Happy Birthday, {short}!"[:40]
    # Copy that is actually written, not manufactured: the caller's hint
    # first (the calling agent is itself a model with the profile in hand),
    # then a server-side model when configured, then template lines openly
    # flagged as fallback so nobody mistakes them for writing.
    copy_source = "template-fallback"
    if message_hint.strip():
        message = message_hint.strip()[:240]
        copy_source = "caller-hint"
    else:
        import asyncio as _aio2
        try:
            llm_line = await _aio2.to_thread(_cards.generate_copy_llm, prof, tone)
        except Exception:
            llm_line = None
        if llm_line:
            message = llm_line[:240]
            copy_source = "server-llm"
        else:
            lines = _cards.message_lines(prof, tone)
            message = (lines[0]["text"][:240] if lines else "")
    if not signature.strip():
        return [TextContent(type="text", text=_j({"ok": False, "error": "signature required — ask the human who signs the card (never default to the recipient)"}))]
    sig = signature.strip()[:40]
    spec = {"template": "birthday_4photo", "format": "5x7",
            "photos": [{"photo_id": pid, "crop": [0, 0, 1, 1],
                        "focus": [0.5, 0.5], "cutout": ""} for pid in pids],
            "headline": title, "recipient": name, "sender": sig,
            "inside_message": message, "title_vibe": vibe or "playful_balloons"}
    saved = await _call("POST", "/api/cards/designs",
                        {"owner": owner, "spec": spec}, api_key=api_key, owner_sig=owner_sig)
    if not saved.get("ok"):
        return [TextContent(type="text", text=_j(saved))]
    d = saved["design"]
    # Generative title zone filled inline when a key exists — the normal
    # path generates, never punts to a second tool. Any failure keeps the
    # serif fallback and says why.
    title_note = "serif-fallback"
    tkey = await _maybe_title_art(title, vibe or "playful_balloons",
                                  owner or "anon", d["id"], api_key, owner_sig)
    if tkey:
        upd = await _call("POST", "/api/cards/designs",
                          {"owner": owner, "id": d["id"],
                           "expected_revision": d["revision"],
                           "spec": {**d.get("spec", {}), "title_art_key": tkey}},
                          api_key=api_key, owner_sig=owner_sig)
        if upd.get("ok"):
            d = upd["design"]
            title_note = "generated"
        else:
            title_note = "generate-ok-save-failed"
    bundle = await _card_spread_bundle(d["id"], d["revision"], owner, api_key, owner_sig=owner_sig)
    exp = await _call("POST", f"/api/cards/{d['id']}/render",
                      {"owner": owner, "revision": d["revision"], "kind": "export"}, api_key=api_key, owner_sig=owner_sig)
    body = {"ok": True, "design_id": d["id"], "revision": d["revision"],
            "template_id": "birthday_4photo",
            "copy_source": copy_source, "title_art": title_note,
            "previews": {**(bundle.get("views") or {}),
                         "print_pdf": f"/api/cards/{d['id']}/r{d['revision']}/export"},
            "proof_url": saved.get("proof_url", ""),
            "export": (exp.get("job") or {}).get("id", ""),
            "render_error": bundle.get("error", ""),
            "hint": "Send the human the proof_url. Tweak copy via oddhobb_edit_card_copy, art via oddhobb_regenerate_title_art, sell via oddhobb_checkout_card."}
    try:
        return [TextContent(type="text", text=_j(body)),
                _contact_block(owner, d["id"], d["revision"])]
    except Exception as e:  # noqa: BLE001
        body["contact_error"] = str(e)[:150]
        return [TextContent(type="text", text=_j(body))]


async def oddhobb_deal_cards(person: str = "", subject_id: str = "",
                             occasion: str = "birthday", tone: str = "funny",
                             signature: str = "", owner: str = "", api_key: str = "",
                             owner_sig: str = "") -> list:
    """Deal four varied buyable cards in ONE call: distinct templates across
    the birthday set (photo-count aware) with distinct copy angles, all saved
    as revision 1 with views + proof_urls. The human opens the proofs, picks
    one, edits it, buys it. Templates are the variety engine — reuse is the
    point. Illustrated (fullbleed) variety unlocks with a provider key;
    today the deal is the photo line."""
    from mcp.types import TextContent
    from backend import cards as _cards
    if not signature.strip():
        return [TextContent(type="text", text=_j({"ok": False, "error": "signature required — ask the human who signs the cards (never default to the recipient)"}))]
    people = await _call("GET", "/api/oddhobb/people?owner=" + (owner or "anon"),
                         api_key=api_key, owner_sig=owner_sig)
    sub = _find_subject(people, person, subject_id)
    if not sub:
        return [TextContent(type="text", text=_j({"ok": False, "error": "unknown subject — check oddhobb_people first"}))]
    label = _cards.display_label(sub.get("name", ""), sub.get("relationship", ""))
    pids: list[str] = []
    try:
        from backend import subject_assets as _sa
        res = _sa.resolve(sub.get("id", ""), owner or "anon")
        ranked = sorted((res.get("body_candidates") or []) + (res.get("face_candidates") or []),
                        key=lambda c: float(c.get("quality", c.get("face_quality", 0))), reverse=True)
        seen: set[str] = set()
        for c in ranked:
            aid = str(c.get("asset_id") or "")
            if aid and aid not in seen:
                seen.add(aid)
                pids.append(aid)
        pids = _cards.solo_first(owner or "anon", pids)[:8]
    except Exception:  # noqa: BLE001
        pids = []
    if not pids:
        return [TextContent(type="text", text=_j({"ok": False, "error": "need at least 1 confirmed photo — upload one and I'll deal four"}))]
    ladder = [("birthday_4photo", 4, 4), ("birthday_wall", 2, 5),
              ("birthday_arch", 1, 1), ("birthday_news", 1, 1),
              ("birthday_gold", 1, 1), ("birthday_dots", 1, 3),
              ("portrait", 1, 1), ("typography", 0, 0)]
    picks = [(tid, lo, hi) for tid, lo, hi in ladder if len(pids) >= lo][:4]
    tones: list[str] = []
    for t in [tone or "funny", "warm", "dry", "funny"]:
        if t not in tones:
            tones.append(t)
    sig = signature.strip()[:40]
    title = f"Happy Birthday, {label}!"[:40]
    prof = {"name": label, "relationship": sub.get("relationship", ""),
            "interests": sub.get("interests", []), "memories": sub.get("memories", [])}
    cards_out = []
    for i, (tid, lo, hi) in enumerate(picks):
        t = tones[i % len(tones)]
        lines = _cards.message_lines(prof, t)
        message = (lines[i % len(lines)]["text"][:240] if lines else "")
        if tid == "typography":
            use_pids: list[str] = []
        elif tid == "birthday_4photo":
            use_pids = pids[:4]
        elif tid in ("birthday_wall", "birthday_dots"):
            use_pids = pids[:min(len(pids), hi)]
        else:
            use_pids = pids[:1]
        spec = {"template": tid, "format": "5x7",
                "photos": [{"photo_id": pid, "crop": [0, 0, 1, 1],
                            "focus": [0.5, 0.5], "cutout": ""} for pid in use_pids],
                "headline": title, "recipient": label, "sender": sig,
                "inside_message": message, "title_vibe": "playful_balloons"}
        saved = await _call("POST", "/api/cards/designs",
                            {"owner": owner, "spec": spec}, api_key=api_key, owner_sig=owner_sig)
        if not saved.get("ok"):
            continue
        d = saved["design"]
        bundle = await _card_spread_bundle(d["id"], d["revision"], owner, api_key, owner_sig=owner_sig)
        cards_out.append({"design_id": d["id"], "revision": d["revision"],
                          "template_id": tid, "tone": t, "headline": title,
                          "message": message, "proof_url": saved.get("proof_url", ""),
                          "views": bundle.get("views", {}),
                          "render_error": bundle.get("error", "")})
    if not cards_out:
        return [TextContent(type="text", text=_j({"ok": False, "error": "could not deal any card — check photos and try again"}))]
    return [TextContent(type="text", text=_j(
        {"ok": True, "cards": cards_out,
         "hint": "Send the human the four proof_urls. They pick one, tweak it via oddhobb_edit_card_copy, buy via oddhobb_checkout_card."}))]


async def oddhobb_attach_card_art(design_id: str = "", front_art_url: str = "",
                                  inside_art_url: str = "", back_art_url: str = "",
                                  headline: str = "", recipient: str = "",
                                  sender: str = "", inside_message: str = "",
                                  headline_baked: bool = True, art_source: str = "",
                                  prompt: str = "", owner: str = "", api_key: str = "",
                                  owner_sig: str = "") -> list:
    """Pin third-party/generated art to a NEW fullbleed revision (creates the
    design when design_id is empty). Server-side fetch + aspect/size/face
    validation, then preview + spread auto-render. Returns views, proof_url,
    and a triptych image. Attach never mutates — edits mint revisions."""
    from mcp.types import TextContent
    if not (front_art_url or "").strip():
        return [TextContent(type="text", text=_j({"ok": False, "http_status": 400,
                             "error": "front_art_url is required"}))]
    saved = await _call("POST", "/api/cards/attach-art",
                        {"owner": owner, "design_id": design_id,
                         "front_art_url": front_art_url,
                         "inside_art_url": inside_art_url,
                         "back_art_url": back_art_url,
                         "headline": headline, "recipient": recipient,
                         "sender": sender, "inside_message": inside_message,
                         "headline_baked": bool(headline_baked),
                         "art_source": art_source, "prompt": prompt},
                        api_key=api_key, owner_sig=owner_sig)
    if not saved.get("ok"):
        return [TextContent(type="text", text=_j(saved))]
    d = saved["design"]
    bundle = await _card_spread_bundle(d["id"], d["revision"], owner, api_key, owner_sig=owner_sig)
    exp = await _call("POST", f"/api/cards/{d['id']}/render",
                      {"owner": owner, "revision": d["revision"], "kind": "export"}, api_key=api_key, owner_sig=owner_sig)
    body = {"ok": True, "design_id": d["id"], "revision": d["revision"],
            "template_id": "birthday_fullbleed",
            "previews": {**(bundle.get("views") or {}),
                         "print_pdf": f"/api/cards/{d['id']}/r{d['revision']}/export"},
            "proof_url": saved.get("proof_url", ""),
            "warnings": saved.get("warnings", []),
            "export": (exp.get("job") or {}).get("id", ""),
            "render_error": bundle.get("error", ""),
            "hint": "Send the human the proof_url. Message/signature edits via oddhobb_edit_card_copy keep the art; sell via oddhobb_checkout_card."}
    try:
        return [TextContent(type="text", text=_j(body)),
                _contact_block(owner, d["id"], d["revision"])]
    except Exception as e:  # noqa: BLE001
        body["contact_error"] = str(e)[:150]
        return [TextContent(type="text", text=_j(body))]


async def _maybe_title_art(headline: str, vibe: str, owner: str,
                             design_id: str, api_key: str = "",
                             owner_sig: str = "") -> str | None:
    """Attempt generative title art inline. Returns a storage key or None.
    Contract enforced downstream by cards.fit_title_art (exact 930×320 RGBA
    with real transparency) — opaque or malformed output is rejected and the
    card keeps serif. Never raises; every failure path is silent fallback."""
    import os as _os
    if not _os.environ.get("FAL_KEY"):
        return None
    try:
        from backend.card_scenes import title_prompt, TITLE_VIBES
        from backend import cards as _cards
        v = vibe if vibe in TITLE_VIBES else "playful_balloons"
        from backend.creative.providers import fal as _fal
        rid = _fal._submit("fal-ai/flux/dev",
                           {"prompt": title_prompt(headline, v),
                            "image_size": "landscape_4_3", "num_images": 1},
                           _os.environ["FAL_KEY"])
        res = _fal._result("fal-ai/flux/dev", rid, _os.environ["FAL_KEY"])
        imgs = ((res.get("response") or res).get("images") or [])
        if not imgs:
            return None
        import urllib.request as _url
        from pathlib import Path as _P
        from PIL import Image as _I
        tmp, _ = _url.urlretrieve(imgs[0]["url"])
        try:
            fitted = _cards.fit_title_art(_I.open(_P(tmp)))
        finally:
            _P(tmp).unlink(missing_ok=True)
        if fitted is None:
            return None
        _fal.log_spend(owner=owner, adapter="fal.title_art",
                       endpoint="fal-ai/flux/dev", est_cost_usd=0.025,
                       request_id=rid)
        key = f"owners/{_cards.storage._slug(owner)}/cards/{design_id}/title-art.png"
        dest = _cards.cached(key)
        fitted.save(dest, "PNG")
        _cards.storage.put(dest, key)
        return key
    except Exception:
        return None


async def oddhobb_regenerate_title_art(design_id: str, vibe: str = "",
                                       owner: str = "", api_key: str = "",
                                       owner_sig: str = "") -> str:
    """Generate the title-art PNG for a canonical card (fal.ai, ask-first
    spend logged to the fal ledger). Without FAL_KEY returns 503 honestly —
    the house-serif fallback keeps rendering until art exists."""
    import os as _os
    if not _os.environ.get("FAL_KEY"):
        return _j({"ok": False, "http_status": 503,
                   "error": "FAL_KEY not configured — title renders in house serif until art is generated"})
    cur = await _call("GET", "/api/cards/designs/" + design_id +
                      "?owner=" + (owner or "anon"), api_key=api_key, owner_sig=owner_sig)
    if not cur.get("ok"):
        return _j(cur)
    spec = (cur.get("design") or {}).get("spec") or {}
    rev = (cur.get("design") or {}).get("revision", 1)
    if (spec.get("template") or "") != "birthday_4photo":
        return _j({"ok": False, "error": "title art is canonical-template only"})
    from backend.card_scenes import title_prompt, TITLE_VIBES
    v = vibe or spec.get("title_vibe") or "playful_balloons"
    if v not in TITLE_VIBES:
        return _j({"ok": False, "error": f"vibe must be one of {list(TITLE_VIBES)}"})
    try:
        from backend.creative.providers import fal as _fal
        rid = _fal._submit("fal-ai/flux/dev",
                           {"prompt": title_prompt(spec.get("headline", ""), v),
                            "image_size": "landscape_4_3", "num_images": 1},
                           _os.environ["FAL_KEY"])
        res = _fal._result("fal-ai/flux/dev", rid, _os.environ["FAL_KEY"])
        imgs = ((res.get("response") or res).get("images") or [])
        if not imgs:
            return _j({"ok": False, "error": f"fal produced no image: {str(res)[:150]}"})
        import urllib.request as _url
        from backend import cards as _cards
        tmp, _ = _url.urlretrieve(imgs[0]["url"])
        from pathlib import Path as _P
        from PIL import Image as _I
        try:
            fitted = _cards.fit_title_art(_I.open(_P(tmp)))
        finally:
            _P(tmp).unlink(missing_ok=True)
        if fitted is None:
            return _j({"ok": False, "http_status": 422,
                       "error": "fal output rejected by the title contract (needs real transparency at 930×320) — serif stands"})
        _fal.log_spend(owner=owner or "anon", adapter="fal.title_art",
                       endpoint="fal-ai/flux/dev", est_cost_usd=0.025, request_id=rid)
        key = f"owners/{_cards.storage._slug(owner or 'anon')}/cards/{design_id}/title-art.png"
        dest = _cards.cached(key)
        fitted.save(dest, "PNG")
        _cards.storage.put(dest, key)
        saved = await _call("POST", "/api/cards/designs",
                            {"owner": owner, "id": design_id, "expected_revision": rev,
                             "spec": {**spec, "title_art_key": key, "title_vibe": v}}, api_key=api_key, owner_sig=owner_sig)
        return _j({**saved, "title_request_id": rid})
    except Exception as e:  # noqa: BLE001
        return _j({"ok": False, "error": str(e)[:200]})


async def oddhobb_edit_card_copy(design_id: str, owner: str = "", headline: str = "",
                                 message: str = "", signature: str = "",
                                 api_key: str = "",
                                 owner_sig: str = "") -> str:
    """Edit canonical copy (headline ≤40, message ≤240, signature ≤40) → new
    revision. Empty fields keep their current values. Renders the new
    revision (preview + spread + export) so checkout can follow at once —
    art is untouched, only words move."""
    cur = await _call("GET", "/api/cards/designs/" + design_id +
                      "?owner=" + (owner or "anon"), api_key=api_key, owner_sig=owner_sig)
    if not cur.get("ok"):
        return _j(cur)
    d = cur["design"]
    spec = dict(d.get("spec") or {})
    if headline.strip():
        spec["headline"] = headline.strip()[:40]
    if message.strip():
        spec["inside_message"] = message.strip()[:240]
        inner = dict(spec.get("inside") or {})
        right = dict(inner.get("right") or {})
        right["message"] = message.strip()[:240]
        inner["right"] = right
        spec["inside"] = inner
    if signature.strip():
        spec["sender"] = signature.strip()[:40]
    saved = await _call("POST", "/api/cards/designs",
                        {"owner": owner, "id": design_id,
                         "expected_revision": d.get("revision", 1), "spec": spec}, api_key=api_key, owner_sig=owner_sig)
    if not saved.get("ok"):
        return _j(saved)
    nd = saved["design"]
    jobs = []
    for kind in ("preview", "spread", "export"):
        r = await _call("POST", f"/api/cards/{nd['id']}/render",
                        {"owner": owner, "revision": nd["revision"], "kind": kind},
                        api_key=api_key, owner_sig=owner_sig)
        jobs.append((r.get("job") or {}).get("id", ""))
    out = dict(saved)
    out["render_jobs"] = jobs
    out["hint"] = ("New revision rendered — proof_url shows it; "
                   "oddhobb_checkout_card when ready.")
    return _j(out)


async def oddhobb_checkout_card(design_id: str, revision: int, owner: str = "",
                                qty: int = 1, idempotency_key: str = "",
                                api_key: str = "",
                                owner_sig: str = "") -> str:
    """Pin a canonical revision and buy it (£2.99 → Shopify draft). 409s when
    that revision has no passing export render — render first, then pay."""
    return _j(await _call("POST", f"/api/cards/{design_id}/checkout",
                         {"owner": owner, "revision": revision, "qty": qty,
                          "idempotency_key": idempotency_key or f"canonical-{design_id}-r{revision}"}, api_key=api_key, owner_sig=owner_sig))


async def oddhobb_checkout_card(design_id: str, revision: int, owner: str = "",
                                qty: int = 1, idempotency_key: str = "",
                                api_key: str = "",
                                owner_sig: str = "") -> str:
    """Pin a canonical revision and buy it (£2.99 → Shopify draft). 409s when
    that revision has no passing export render — render first, then pay."""
    return _j(await _call("POST", f"/api/cards/{design_id}/checkout",
                         {"owner": owner, "revision": revision, "qty": qty,
                          "idempotency_key": idempotency_key or f"canonical-{design_id}-r{revision}"}, api_key=api_key, owner_sig=owner_sig))


# ── canonical six: intent in, finished products out ───────────────────
# People, make, change, get, add_media, buy. No layout, no fonts, no jobs,
# no providers, no capsules. Backend operations stay internal; the agent
# supplies person + request and receives finished, buyable things.
# Auth args stay accepted but optional: connection Bearer wins, then
# explicit api_key, then anon. The agent never needs to reason about them.

def _bearer_key(ctx=None) -> str:
    """API key from the MCP connection itself (Authorization header),
    if the framework exposes it. Best-effort: "" when unavailable."""
    try:
        rc = getattr(ctx, "request_context", None)
        req = getattr(rc, "request", None) if rc is not None else None
        if req is None:
            sess = getattr(rc, "session", None) if rc is not None else None
            req = getattr(sess, "_request", None) if sess is not None else None
        headers = getattr(req, "headers", {}) or {}
        auth = headers.get("authorization", "") or headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
    except Exception:
        pass
    return ""


def _resolve_owner(owner: str = "", api_key: str = "", ctx=None) -> str:
    """Who is calling. Explicit owner wins (back-compat); else the key
    holder — user handle, or the PARENT handle for delegated agent keys
    (agents act as their customer); else anon."""
    if (owner or "").strip():
        return owner.strip()[:80]
    key = (api_key or "").strip() or _bearer_key(ctx)
    if not key:
        return "anon"
    try:
        from backend import db as _db
        with _db.connect() as c:
            u = _db.get_user_by_api_key(c, key)
            if u:
                return u["handle"]
            a = _db.get_agent_by_key(c, key)
            if a and a["status"] == "active":
                return a["parent_handle"]
    except Exception:
        pass
    return "anon"


def _env(*, status="ready", id="", summary="", artifacts=None,
         price_cents=None, next_actions=None, requires_action=None,
         extra=None) -> dict:
    """Canonical public envelope. Stable keys; legacy callers keep working
    because their fields ride along inside extra."""
    d: dict = {"ok": True, "status": status, "id": id, "summary": summary,
               "artifacts": artifacts or [],
               "next_actions": next_actions or ["change", "buy"]}
    if price_cents is not None:
        d["price"] = {"amount_cents": price_cents, "currency": "GBP"}
    if requires_action is not None:
        d["requires_action"] = requires_action
    if extra:
        d.update(extra)
    return d


def _artifact_list(design_id: str, rev: int, owner: str) -> list:
    from backend import config as _cfg
    base = (_cfg.PUBLIC_BASE or "https://oddhobb.com").rstrip("/")
    acct = f"?owner={owner}"
    return [
        {"kind": "front", "url": f"{base}/backend/api/cards/{design_id}/r{rev}/preview{acct}"},
        {"kind": "inside", "url": f"{base}/backend/api/cards/{design_id}/r{rev}/inside{acct}"},
        {"kind": "back", "url": f"{base}/backend/api/cards/{design_id}/r{rev}/back{acct}"},
    ]


async def oddhobb_recommend(person: str = "", subject_id: str = "",
                            occasion: str = "birthday", budget_cents: int = 0,
                            vibe: str = "", tone: str = "funny",
                            signature: str = "", owner: str = "",
                            api_key: str = "", owner_sig: str = "") -> list:
    """Rank published recipes for a person and compile the top three into
    finished products (saved revisions + preview renders + proof_urls).
    Without a signature the ideas return uncompiled (preview_status
    needs-signature) — the signer is asked once, never defaulted."""
    from mcp.types import TextContent
    from backend.recipes import matcher as _rmatch
    from backend.recipes import registry as _rreg
    from backend.recipes import compiler as _comp
    people = await _call("GET", "/api/oddhobb/people?owner=" + (owner or "anon"),
                         api_key=api_key, owner_sig=owner_sig)
    sub = _find_subject(people, person, subject_id)
    if not sub:
        return [TextContent(type="text", text=_j({"ok": False, "error": "unknown subject — check oddhobb_people first"}))]
    prof = {"name": sub.get("name", ""), "relationship": sub.get("relationship", ""),
            "interests": sub.get("interests", []), "memories": sub.get("memories", [])}
    subject = {"id": sub.get("id", ""), **prof}
    try:
        from backend import subject_assets as _sa
        pool = _sa.resolve(sub.get("id", ""), owner or "anon")
        nphotos = len({str(c.get("asset_id") or "") for c in
                       (pool.get("body_candidates") or []) + (pool.get("face_candidates") or [])
                       if c.get("asset_id")})
    except Exception:
        nphotos = 0
    brief = _comp.build_brief(subject=subject, occasion=occasion, vibe=vibe,
                              photo_count=nphotos)
    matches = _rmatch.match(brief, _rreg.published(), limit=5)
    if not matches:
        return [TextContent(type="text", text=_j(
            {"ok": False, "error": "no published recipe fits — upload photos first",
             "brief": {"occasion": brief["occasion"], "photo_count": nphotos}}))]
    recs = []
    do_compile = bool(signature.strip())
    for m in matches[:3]:
        if not do_compile:
            recs.append({"idea_id": f"idea_{m['id']}", "recipe": m["id"],
                         "version": m["version"], "score": m["score"],
                         "why": "; ".join(m["reasons"]),
                         "price_cents": m["price_cents"],
                         "preview_status": "needs-signature"})
            continue
        c = await asyncio.to_thread(
            _comp.compile, owner or "anon", m["id"], subject=subject,
            occasion=occasion, vibe=vibe, tone=tone, message_hint="",
            signature=signature)
        if not c.get("ok"):
            continue
        d = c["design"]
        recs.append({"idea_id": f"idea_{m['id']}", "recipe": m["id"],
                     "version": m["version"], "score": m["score"],
                     "why": "; ".join(m["reasons"]),
                     "price_cents": m["price_cents"],
                     "design_id": d["id"], "revision": d["revision"],
                     "copy_source": c.get("copy_source", ""),
                     "proof_url": c.get("proof_url", ""),
                     "preview_status": "ready"})
    return [TextContent(type="text", text=_j(
        {"ok": True, "ideas": recs,
         "hint": "Send the human the proof_urls. oddhobb_make realizes one fully; "
                 "oddhobb_variants deals more; oddhobb_checkout_card buys."}))]


async def _cardgen_make(who, key_arg, owner_sig, sub, prof, occasion, tone, count):
    """Start cardgen jobs for the best castable templates. None = fall back."""
    profile = {**prof, "tone": tone, "occasion": occasion,
               "recipient": (prof.get("relationship") or "").title() or prof.get("name", "")}
    rec = await _call("POST", "/api/cardgen/recommend",
                      {"owner": who, "subject_id": sub.get("id", ""), "occasion": occasion,
                       "profile": profile}, api_key=key_arg, owner_sig=owner_sig)
    if not rec.get("ok"):
        return None
    ready = rec.get("ready") or []
    if not ready:
        need = sorted({s for b in (rec.get("blocked") or []) for s in b.get("shortfall", [])})
        return _env(status="needs_input", summary=rec.get("tip") or
                    f"I need different photos of {prof.get('name') or 'them'}.",
                    requires_action={"type": "add_media", "subject_id": sub.get("id", ""),
                                     "message": "; ".join(need)[:300] or "Add a few clear photos."},
                    next_actions=[])
    jobs = []
    for r in ready[:max(1, min(int(count or 4), 4))]:
        mk = await _call("POST", "/api/cardgen/make",
                         {"owner": who, "subject_id": sub.get("id", ""), "template_id": r["template_id"],
                          "occasion": occasion, "profile": profile}, api_key=key_arg, owner_sig=owner_sig)
        if not mk.get("ok"):
            if not jobs:
                return None          # e.g. 503 FAL_KEY missing -> legacy shelf
            continue
        jobs.append({"id": mk["job_id"], "template": r["template_id"], "status": "rendering",
                     "photos": r.get("photos")})
    if not jobs:
        return None
    return _env(status="working", id=jobs[0]["id"],
                summary=f"Painting {len(jobs)} cards of {prof.get('name') or 'them'} from their photos (about a minute each).",
                next_actions=["get"],
                extra={"options": jobs, "engine": "cardgen",
                       "hint": "Call oddhobb_get(design_id=<job id>) for each; it returns the finished card when ready."})


async def oddhobb_card_recommend(subject_id: str, occasion: str = "birthday",
                                 owner: str = "", api_key: str = "", owner_sig: str = "") -> str:
    """Which card templates this person's uploaded photos can make, and what the
    others still need ("needs a happy solo photo of them"). Labels photos once."""
    return _j(await _call("POST", "/api/cardgen/recommend",
                          {"owner": owner, "subject_id": subject_id, "occasion": occasion},
                          api_key=api_key, owner_sig=owner_sig))


async def oddhobb_card_generate(subject_id: str, template_id: str, occasion: str = "birthday",
                                title: str = "", inside: str = "", sender: str = "", recipient: str = "",
                                owner: str = "", api_key: str = "", owner_sig: str = "") -> str:
    """Generate one card with cardgen from the person's real photos. Optional
    copy overrides. Returns a job id; oddhobb_get(design_id=job_id) polls it."""
    copy = {k: v for k, v in {"title": title, "inside": inside}.items() if v}
    return _j(await _call("POST", "/api/cardgen/make",
                          {"owner": owner, "subject_id": subject_id, "template_id": template_id,
                           "occasion": occasion, "copy": copy,
                           "profile": {"sender": sender, "recipient": recipient}},
                          api_key=api_key, owner_sig=owner_sig))


async def oddhobb_make(subject_id: str = "", person: str = "",
                        request: str = "", product_type: str = "greeting_card",
                        budget_cents: int = 0, count: int = 4,
                        owner: str = "", api_key: str = "",
                        owner_sig: str = "", ctx=None) -> list:
    """Make finished personalised things: brief, rank, compile, render, QC.
    Returns ready options with views — never idea IDs, never template names.
    Unsigned previews are fine; the signer is asked once, at buy time."""
    from mcp.types import TextContent
    from backend.recipes import matcher as _rmatch
    from backend.recipes import registry as _rreg
    from backend.recipes import compiler as _comp
    who = _resolve_owner(owner, api_key, ctx)
    key_arg = api_key or _bearer_key(ctx)
    if (product_type or "greeting_card") != "greeting_card":
        return [TextContent(type="text", text=_j(_env(
            status="needs_input", summary="Only greeting cards so far.",
            requires_action={"type": "change_request",
                             "message": "I make greeting cards — try 'birthday card for Dad'."},
            next_actions=[])))]
    people = await _call("GET", "/api/oddhobb/people?owner=" + who,
                         api_key=key_arg, owner_sig=owner_sig)
    sub = _find_subject(people, person, subject_id)
    if not sub:
        return [TextContent(type="text", text=_j(
            {"ok": False, "error": "unknown subject — check oddhobb_people first"}))]
    rq = str(request or "")
    rl = rq.lower()
    occasion = "birthday"
    for o in ("christmas", "valentine", "anniversary", "graduation",
              "retirement", "new_baby", "new baby"):
        if o in rl:
            occasion = o.replace(" ", "_")
            break
    tone = "funny"
    for t in ("dry", "warm", "roast", "mean", "savage", "short", "sweet"):
        if t in rl:
            tone = "dry" if t in ("mean", "savage", "roast") else t
            break
    prof = {"name": sub.get("name", ""), "relationship": sub.get("relationship", ""),
            "interests": sub.get("interests", []), "memories": sub.get("memories", [])}
    subject = {"id": sub.get("id", ""), **prof}
    # Canonical path: cardgen (generative, cast from the person's real photos).
    # The legacy PIL shelf below runs only when cardgen can't start (no FAL_KEY).
    cg = await _cardgen_make(who, key_arg, owner_sig, sub, prof, occasion, tone, count)
    if cg is not None:
        return [TextContent(type="text", text=_j(cg))]
    try:
        from backend import subject_assets as _sa
        pool = _sa.resolve(sub.get("id", ""), who)
        nphotos = len({str(c.get("asset_id") or "") for c in
                       (pool.get("body_candidates") or []) + (pool.get("face_candidates") or [])
                       if c.get("asset_id")})
    except Exception:
        nphotos = 0
    brief = _comp.build_brief(subject=subject, occasion=occasion,
                              vibe=rq[:200], photo_count=nphotos)
    matches = _rmatch.match(brief, _rreg.published(), limit=5)
    if not matches:
        return [TextContent(type="text", text=_j(_env(
            status="needs_input",
            summary=f"I need photos of {prof.get('name') or 'them'} first.",
            requires_action={"type": "add_media", "subject_id": sub.get("id", ""),
                             "message": f"I need a few clear photos to make these — add {4 - nphotos} more."},
            next_actions=[])))]
    want = max(1, min(int(count or 4), 4))
    tones = []
    for t in [tone, "warm", "dry", "funny"]:
        if t not in tones:
            tones.append(t)
    options = []
    for i in range(want):
        m = matches[i % len(matches)]
        c = await asyncio.to_thread(
            _comp.compile, who, m["id"], subject=subject, occasion=occasion,
            vibe=rq[:200], tone=tones[i % len(tones)], message_hint="",
            signature="", variation=i)
        if not c.get("ok"):
            continue
        d = c["design"]
        bundle = await _card_spread_bundle(d["id"], d["revision"], who,
                                           api_key=key_arg, owner_sig=owner_sig)
        views = bundle.get("views_abs") or bundle.get("views") or {}
        options.append({
            "id": d["id"], "creation_id": d["id"], "recipe": m["id"],
            "name": (d.get("spec") or {}).get("headline", ""),
            "price_cents": m["price_cents"],
            "views": {k: views.get(k, "") for k in ("front", "inside", "back")},
            "proof_url": c.get("proof_url", ""),
        })
        if bundle.get("error"):
            options[-1]["render_note"] = bundle["error"]
    if not options:
        return [TextContent(type="text", text=_j(
            {"ok": False, "error": "could not compile — check photos and try again"}))]
    first = options[0]
    return [TextContent(type="text", text=_j(_env(
        status="ready", id=first["id"],
        summary=f"Made {len(options)} for {(prof.get('name') or 'them')} — pick one.",
        price_cents=first["price_cents"],
        next_actions=["change", "buy"],
        extra={"options": options,
               "design_id": first["id"],
               "proof_url": first.get("proof_url", "")})))]


async def oddhobb_variants(design_id: str = "", idea_id: str = "",
                           vibe: str = "", tone: str = "funny",
                           signature: str = "", n: int = 3,
                           owner: str = "", api_key: str = "",
                           owner_sig: str = "") -> list:
    """More like this / change vibe: recompile the same recipe with new
    tones, copy, and photo slices. Returns fresh finished designs."""
    from mcp.types import TextContent
    from backend.recipes import compiler as _comp
    if not signature.strip():
        return [TextContent(type="text", text=_j(
            {"ok": False, "error": "signature required — ask the human who signs the cards"}))]
    if design_id:
        cur = await _call("GET", "/api/cards/designs/" + design_id +
                          "?owner=" + (owner or "anon"), api_key=api_key, owner_sig=owner_sig)
        if not cur.get("ok"):
            return [TextContent(type="text", text=_j(cur))]
        spec = ((cur.get("design") or {}).get("spec")) or {}
        recipe_id = spec.get("recipe_id") or "birthday_four_photos_party_title_v1"
        # original star: first photo slot with a confirmed subject wins
        subject_id = ""
        try:
            from backend import db as _db
            first_pid = ((spec.get("photos") or [{}])[0] or {}).get("photo_id", "")
            if first_pid:
                with _db.connect() as c:
                    hit = c.execute(
                        "SELECT subject_id FROM photo_subjects WHERE photo_id=? "
                        "AND confirmed=1 LIMIT 1", (first_pid,)).fetchone()
                    subject_id = dict(hit)["subject_id"] if hit else ""
        except Exception:
            subject_id = ""
    elif (idea_id or "").startswith("idea_"):
        recipe_id = idea_id[5:]
        subject_id = ""
    else:
        return [TextContent(type="text", text=_j(
            {"ok": False, "error": "pass design_id or idea_id"}))]
    people = await _call("GET", "/api/oddhobb/people?owner=" + (owner or "anon"),
                         api_key=api_key, owner_sig=owner_sig)
    subs = ((people.get("people") or []) if isinstance(people, dict) else [])
    by_id = {((s.get("subject") or {}).get("id")): s for s in subs}
    target = by_id.get(subject_id, {})
    if not target and subs:
        target = subs[0]
    if not (target.get("subject") or {}).get("id"):
        return [TextContent(type="text", text=_j({"ok": False, "error": "no subject to vary — check oddhobb_people first"}))]
    ts = target.get("subject") or {}
    tp = (target.get("profile") or {}).get("profile", {})
    subject = {"id": ts.get("id", ""),
               "name": tp.get("name", ts.get("name", "")),
               "relationship": tp.get("relationship", ts.get("relationship", "")),
               "interests": tp.get("interests", []),
               "memories": tp.get("memories", [])}
    tones = []
    for t in [tone or "funny", "warm", "dry", "funny"]:
        if t not in tones:
            tones.append(t)
    out = []
    for i in range(max(1, min(int(n or 3), 5))):
        c = await asyncio.to_thread(
            _comp.compile, owner or "anon", recipe_id, subject=subject,
            occasion="birthday", vibe=vibe or tones[i % len(tones)],
            tone=tones[i % len(tones)], message_hint="",
            signature=signature, variation=i + 1)
        if not c.get("ok"):
            continue
        d = c["design"]
        out.append({"design_id": d["id"], "revision": d["revision"],
                    "tone": tones[i % len(tones)],
                    "copy_source": c.get("copy_source", ""),
                    "proof_url": c.get("proof_url", "")})
    if not out:
        return [TextContent(type="text", text=_j({"ok": False, "error": "could not vary — check photos and try again"}))]
    return [TextContent(type="text", text=_j(
        {"ok": True, "variants": out,
         "hint": "Send the human the proof_urls; oddhobb_checkout_card buys."}))]


async def oddhobb_get(design_id: str, revision: int = 0, owner: str = "",
                      api_key: str = "", owner_sig: str = "") -> list:
    """Status + final artifacts for one card: faces, triptych, print PDF,
    proof URL, checkout readiness. Read-only."""
    from mcp.types import TextContent
    if (design_id or "").startswith("cgj_"):
        j = await _call("GET", f"/api/cardgen/jobs/{design_id}?owner=" + (owner or "anon"),
                        api_key=api_key, owner_sig=owner_sig)
        if not j.get("ok") or j.get("status") != "ready":
            return [TextContent(type="text", text=_j(j))]
        design_id, revision = j["design_id"], j["revision"]
    if revision:
        spath = f"/api/cards/{design_id}/scene?revision={revision}&owner=" + (owner or "anon")
    else:
        spath = f"/api/cards/{design_id}/scene?owner=" + (owner or "anon")
    scene = await _call("GET", spath, api_key=api_key, owner_sig=owner_sig)
    if not scene.get("ok"):
        return [TextContent(type="text", text=_j(scene))]
    sc = scene.get("scene") or {}
    rev = sc.get("revision", 0)
    base = f"/api/cards/{design_id}/r{rev}"
    return [TextContent(type="text", text=_j(
        {"ok": True, "design_id": design_id, "revision": rev,
         "artifacts": {"front": f"{base}/preview", "inside": f"{base}/inside",
                       "back": f"{base}/back", "triptych": f"{base}/triptych",
                       "print_pdf": f"{base}/export"},
         "proof_url": scene.get("proof_url", ""),
         "outputs": (sc.get("outputs") or {}),
         "hint": "oddhobb_checkout_card buys this revision."}))]



_TONE_WORDS = {
    "funny": "funny", "funnier": "funny", "hilarious": "funny",
    "dry": "dry", "drier": "dry", "deadpan": "dry", "sarcastic": "dry",
    "warm": "warm", "sweet": "warm", "sweeter": "warm", "kind": "warm",
    "roast": "dry", "mean": "dry", "meaner": "dry", "savage": "dry",
    "short": "short", "shorter": "short", "brief": "short",
}
_VIBE_WORDS = ("golf", "football", "christmas", "dog", "cat", "fishing",
               "music", "retro", "classy", "cute", "silly", "posh")


async def oddhobb_change(design_id: str = "", instruction: str = "",
                         owner: str = "", api_key: str = "",
                         owner_sig: str = "", ctx=None) -> list:
    """Change a finished card with plain words ("less cheesy, more golf").
    New immutable revision, affected ingredients re-rendered. No fonts, no
    coordinates, no crop arrays — intent in, finished revision out."""
    from mcp.types import TextContent
    who = _resolve_owner(owner, api_key, ctx)
    key_arg = api_key or _bearer_key(ctx)
    if not design_id:
        return [TextContent(type="text", text=_j(
            {"ok": False, "error": "pass design_id (creation_id) of the card to change"}))]
    cur = await _call("GET", "/api/cards/designs/" + design_id +
                      "?owner=" + who, api_key=key_arg, owner_sig=owner_sig)
    if not cur.get("ok"):
        return [TextContent(type="text", text=_j(cur))]
    d = cur["design"]
    spec = dict(d.get("spec") or {})
    words = str(instruction or "").lower()
    changed = []
    # tone + vibe from human words
    new_tone = ""
    for w, t in _TONE_WORDS.items():
        if w in words:
            new_tone = t
            break
    vibes = [v for v in _VIBE_WORDS if v in words]
    # photo switch?
    new_pids = None
    if any(w in words for w in ("different photo", "different pictures", "other photo",
                                "other pictures", "more golf", "use more")):
        try:
            from backend import subject_assets as _sa
            from backend import cards as _cards
            first = ((spec.get("photos") or [{}])[0] or {}).get("photo_id", "")
            owner_of = who
            subj = ""
            if first:
                from backend import db as _db
                with _db.connect() as c:
                    hit = c.execute(
                        "SELECT subject_id FROM photo_subjects WHERE photo_id=? "
                        "AND confirmed=1 LIMIT 1", (first,)).fetchone()
                    subj = dict(hit)["subject_id"] if hit else ""
            if subj:
                res = _sa.resolve(subj, owner_of)
                pool = [str(c.get("asset_id") or "") for c in
                        (res.get("body_candidates") or []) + (res.get("face_candidates") or [])
                        if c.get("asset_id")]
                pool = _cards.solo_first(owner_of, list(dict.fromkeys(pool)))
                cur_ids = [s.get("photo_id") for s in (spec.get("photos") or [])]
                fresh = [p for p in pool if p not in cur_ids] + \
                        [p for p in pool if p in cur_ids]
                if fresh[:len(cur_ids)] != cur_ids:
                    new_pids = fresh[:len(cur_ids)]
                    changed.append("photo selection")
        except Exception:
            new_pids = None
    # quoted text becomes the new copy verbatim ("headline should say X")
    import re as _re
    quoted = _re.findall(r'"([^"]{1,240})"', str(instruction or ""))
    new_spec = dict(spec)
    if new_pids:
        new_spec["photos"] = [{"photo_id": pid, "crop": [0, 0, 1, 1],
                               "focus": [0.5, 0.5], "cutout": ""}
                              for pid in new_pids]
    if quoted:
        new_spec["headline"] = quoted[0][:40]
        changed.append("front title")
    if new_tone and new_tone != str((spec.get("inside") or {}).get("_tone", "")):
        try:
            from backend import cards as _cards
            from backend import subjects as _subs
            from backend import db as _db2
            prof = {"name": spec.get("recipient", ""), "interests": [],
                    "memories": []}
            try:
                with _db2.connect() as c2:
                    _first = (new_spec.get("photos") or [{}])[0] or {}
                    hit2 = c2.execute(
                        "SELECT subject_id FROM photo_subjects WHERE photo_id=? "
                        "AND confirmed=1 LIMIT 1",
                        (_first.get("photo_id", ""),)).fetchone()
                    if hit2:
                        pr = _subs.profile_for(
                            c2, who, dict(hit2)["subject_id"])
                        prof = {"name": (pr.get("subject") or {}).get("name", ""),
                                "relationship": "",
                                "interests": ((pr.get("profile") or {}).get("profile", {}) or {}).get("interests", []),
                                "memories": []}
            except Exception:
                pass
            lines = _cards.message_lines(prof, new_tone)
            if lines:
                new_spec["inside_message"] = lines[0]["text"][:240]
                inner = dict(new_spec.get("inside") or {})
                right = dict(inner.get("right") or {})
                right["message"] = lines[0]["text"][:240]
                inner["right"] = right
                new_spec["inside"] = inner
                changed.append("inside copy")
        except Exception:
            pass
    if vibes:
        changed.append("vibe: " + ", ".join(vibes))
    saved = await _call("POST", "/api/cards/designs",
                        {"owner": who, "id": design_id,
                         "expected_revision": d.get("revision", 1),
                         "spec": new_spec},
                        api_key=key_arg, owner_sig=owner_sig)
    if not saved.get("ok"):
        return [TextContent(type="text", text=_j(saved))]
    nd = saved["design"]
    bundle = await _card_spread_bundle(nd["id"], nd["revision"], who,
                                       api_key=key_arg, owner_sig=owner_sig)
    views = bundle.get("views_abs") or bundle.get("views") or {}
    if not changed:
        changed = ["revision (no visible change detected)"]
    try:
        from backend import cards as _cardsmod2
        _change_cents = _cardsmod2.card_price().get("price_cents", 299)
    except Exception:
        _change_cents = 299
    return [TextContent(type="text", text=_j(_env(
        status="ready", id=nd["id"],
        summary=f"Changed {nd['id'][:4]}: {', '.join(changed)}.",
        price_cents=_change_cents,
        next_actions=["change", "buy"],
        extra={"design_id": nd["id"], "revision": nd["revision"],
               "changed": changed,
               "artifacts": [
                   {"kind": "front", "url": views.get("front", "")},
                   {"kind": "inside", "url": views.get("inside", "")},
                   {"kind": "back", "url": views.get("back", "")}],
               "proof_url": saved.get("proof_url", "")})))]


async def oddhobb_add_media(subject_id: str = "", person: str = "",
                            photo_url: str = "", slot_id: str = "",
                            owner: str = "", api_key: str = "",
                            owner_sig: str = "", ctx=None) -> list:
    """Add a photo to a person from a URL (upload it, tag it confirmed).
    The escape hatch for agent-assisted generation: hand back a slot's
    requirements, the agent generates with its own provider, OddHobb takes
    the pixels from here. Slot art never reaches print unvalidated."""
    from mcp.types import TextContent
    who = _resolve_owner(owner, api_key, ctx)
    key_arg = api_key or _bearer_key(ctx)
    if not (photo_url or "").strip():
        return [TextContent(type="text", text=_j(_env(
            status="needs_input", summary="No photo to add.",
            requires_action={"type": "add_media",
                             "message": "Give me a photo URL and whose it is."},
            next_actions=[])))]
    people = await _call("GET", "/api/oddhobb/people?owner=" + who,
                         api_key=key_arg, owner_sig=owner_sig)
    sub = _find_subject(people, person, subject_id)
    if not sub:
        return [TextContent(type="text", text=_j(
            {"ok": False, "error": "unknown subject — check oddhobb_people first"}))]
    import urllib.request as _url
    import urllib.error as _urlerr
    try:
        req = _url.Request((photo_url or "").strip(),
                           headers={"User-Agent": "OddHobb-add-media/1.0"})
        with _url.urlopen(req, timeout=60) as res:
            ctype = (res.headers.get("Content-Type") or "").lower()
            data = res.read(15 * 1024 * 1024 + 1)
    except Exception as e:
        return [TextContent(type="text", text=_j(
            {"ok": False, "error": f"could not fetch photo: {str(e)[:120]}"}))]
    if len(data) > 15 * 1024 * 1024 or \
            not any(t in ctype for t in ("image/png", "image/jpeg", "image/webp", "image/jpg")):
        return [TextContent(type="text", text=_j(
            {"ok": False, "error": "photo must be PNG/JPEG/WebP, 15 MB or smaller"}))]
    import io as _io
    import time as _time
    import uuid as _uuid
    from backend import config as _cfg
    from backend import db as _db
    from backend import storage as _storage
    pid = "pho_" + _uuid.uuid4().hex[:24]
    try:
        from PIL import Image as _I
        with _I.open(_io.BytesIO(data)) as im:
            rgb = im.convert("RGB")
            w, h = rgb.size
        dest = _cfg.DATA / "photos" / f"{pid}.jpg"
        dest.parent.mkdir(parents=True, exist_ok=True)
        rgb.save(dest, "JPEG", quality=90)
        import hashlib as _hl
        sha = _hl.sha256(data).hexdigest()
        skey = f"owners/{_storage._slug(who)}/photos/{pid}.jpg"
        _storage.put(dest, skey)
        with _db.connect() as c:
            c.execute("INSERT INTO photos (id,owner,sha256,r2_key,mime,width,height,bytes,orig_name,created_at,person,source)"
                      " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                      (pid, who, sha, skey, "image/jpeg", w, h, len(data),
                       "agent-upload.jpg", _time.time(),
                       sub.get("name", ""), "agent-media"))
            c.commit()
        from backend import subjects as _subs
        with _db.connect() as c:
            _subs.link_photo(c, pid, sub["id"], confirmed=True,
                             provenance="agent-media")
            c.commit()
    except Exception as e:
        return [TextContent(type="text", text=_j(
            {"ok": False, "error": f"could not store photo: {str(e)[:150]}"}))]
    note = f" Tagged to {sub.get('name') or sub['id']}."
    if slot_id:
        note += f" Offered for slot {slot_id} — it still needs attach-art validation before print."
    return [TextContent(type="text", text=_j(_env(
        status="ready", id=pid, summary=f"Photo added.{note}",
        next_actions=["make"],
        extra={"photo_id": pid, "subject_id": sub["id"],
               "slot_id": slot_id or ""})))]


async def oddhobb_capture_start(subject_id: str='', owner: str='', api_key: str='') -> str:
    """Begin a guided person capture; returns the capture script."""
    return _j(await _call('POST', '/api/capture/start', {'subject_id': subject_id, 'owner': owner}, api_key=api_key))


async def oddhobb_capture_mark(capture_id: str='', kind: str='note', note: str='', api_key: str='') -> str:
    """Timestamp a capture moment (oddhobb.capture_mark)."""
    return _j(await _call('POST', '/api/capture/mark', {'capture_id': capture_id, 'kind': kind, 'note': note}, api_key=api_key))


async def oddhobb_capture_finish(capture_id: str='', owner: str='', api_key: str='') -> str:
    """Close a capture → mannerism manifest lands on the subject profile."""
    return _j(await _call('POST', '/api/capture/finish', {'capture_id': capture_id, 'owner': owner}, api_key=api_key))


async def oddhobb_review(artifact_id: str='', api_key: str='') -> str:
    """Agent eyes: verdict + scores + concrete fix ops for a render. $0.
    Feed it artifact ids from render/status, apply fixes via oddhobb_revise."""
    return _j(await _call('POST', '/api/creative/review', {'artifact_id': artifact_id}, api_key=api_key))


async def oddhobb_revise(project_id: str='', revision: int=0, owner: str='', ops: dict | None=None, render: bool=False, api_key: str='') -> str:
    """Agent hands: ops {copy, mood (happier/funnier/warmer/classier), voice,
    act} → new immutable revision, optionally rendered. The 'make them happier' loop."""
    return _j(await _call('POST', '/api/creative/revise', {'project_id': project_id, 'revision': revision, 'owner': owner, 'ops': ops or {}, 'render': render}, api_key=api_key))


async def oddhobb_joke_ideas(person: str = "", occasion: str = "general",
                              owner: str = "", interests: str = "",
                              memories: str = "", humour: str = "") -> str:
    """Three joke-set variants, zero spend: main (our funniest), darker, and
    personal (matched to their humour + context). Human picks one to render."""
    from backend.funny import variants as _jv
    profile = {"name": person or "Dad",
               "interests": [s.strip() for s in interests.split(",") if s.strip()],
               "memories": [s.strip() for s in memories.split("|") if s.strip()],
               "humour": {"absurd": 0.9} if "absurd" in humour else {}}
    return _j({"ok": True, "variants": _jv.plan_variants({}, profile),
               "hint": "render one with oddhobb_joke_render (approved spend, pennies)"})


async def oddhobb_joke_render(variant_id: str = "", owner: str = "",
                              brief: dict | None = None,
                              approved: bool = False) -> str:
    """Render one variant into a judged set. approved=True spends pennies."""
    from backend.funny import pipeline as _fp, variants as _jv
    b = brief or {}
    profile = {"name": b.get("name", "Dad"), "interests": b.get("interests", []),
               "memories": b.get("memories", []), "humour": b.get("humour", {})}
    out = _fp.run_set(profile, approved=approved)
    return _j(out)


async def oddhobb_joke_pick(owner: str = "", chosen_id: str = "",
                            variants: list | None = None) -> str:
    """Record the human pick as DPO fuel (chosen > rejected). Free."""
    from backend.funny import variants as _jv
    return _j({"ok": True, "pick": _jv.record_pick(owner, chosen_id, variants or [])})


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


async def figg_card_library(owner: str = "", api_key: str = "",
owner_sig: str = "") -> str:
    """Photo library + card scenes. Photo cards need no mesh or Meshy spend. Pass api_key to see your own photos (anon sees the shared demo shelf only)."""
    import urllib.parse
    q = urllib.parse.quote(owner)
    return _j({"photos": await _call("GET", "/api/cards/photos?owner=" + q, api_key=api_key, owner_sig=owner_sig),
               "scenes": await _call("GET", "/api/cards/templates?owner=" + q, api_key=api_key, owner_sig=owner_sig),
               "designs": await _call("GET", "/api/cards/designs?owner=" + q, api_key=api_key, owner_sig=owner_sig)})


async def figg_card_save(spec: dict, owner: str = "", design_id: str = "",
                         expected_revision: int = 0, api_key: str = "",
                         owner_sig: str = "") -> str:
    """Save a photo card: template, format, photos[{photo_id,crop,focus,cutout}], headline, recipient, sender, inside_message.
    This is the photo-composition lane (your picture + type). For illustrated/designed covers
    (movie_poster, comics, news parody) use figg_creative_brief → figg_creative_match → oddhobb_create instead.
    Stamped via=mcp. Same validators as REST/UI (brand locks + no wordmark run in save).
    Done means a product_url the human can buy from — POST checkout next. A preview alone is not done."""
    body = {"owner": owner, "spec": spec, "via": "mcp"}
    if design_id:
        body.update(id=design_id, expected_revision=expected_revision)
    return _j(await _call("POST", "/api/cards/designs", body, api_key=api_key, owner_sig=owner_sig))


async def figg_card_render(design_id: str, revision: int, kind: str = "preview",
                           owner: str = "", api_key: str = "",
                           owner_sig: str = "") -> str:
    """Render saved card preview/spread/export/motion. Returns async job; same revision drives paper and MP4.
    Spread returns all four faces (front, inside halves, back) as showable PNGs.
    Public tier: preview + spread (free CPU). Export/motion need the bridge token."""
    if os.environ.get("PUBLIC_MCP") == "1" and kind not in ("preview", "spread"):
        return _j({"ok": False,
                   "error": "public tier renders preview/spread only — export/motion need the bridge token"})
    return _j(await _call("POST", f"/api/cards/{design_id}/render",
                         {"owner": owner, "revision": revision, "kind": kind}, api_key=api_key, owner_sig=owner_sig))


async def figg_card_scene(design_id: str, owner: str = "", revision: int = 0, api_key: str = "",
owner_sig: str = "") -> str:
    """Get the shared card/video scene manifest and available output capabilities."""
    import urllib.parse
    path="/api/cards/"+urllib.parse.quote(design_id,safe="")+"/scene?owner="+urllib.parse.quote(owner)
    if revision:
        path+="&revision="+str(revision)
    return _j(await _call("GET",path, api_key=api_key, owner_sig=owner_sig))


async def figg_card_job(job_id: str, owner: str = "", api_key: str = "",
owner_sig: str = "") -> str:
    """Check card render job status; ready results include owner-gated download URLs."""
    import urllib.parse
    return _j(await _call("GET", f"/api/cards/jobs/{job_id}?owner=" + urllib.parse.quote(owner), api_key=api_key, owner_sig=owner_sig))


async def figg_card_cutout(photo_id: str, crop: list[float], owner: str = "", api_key: str = "",
owner_sig: str = "") -> str:
    """Remove background after explicitly cropping the subject in a group photo. No face recognition or generative upscale."""
    return _j(await _call("POST", "/api/cards/cutouts", {"owner": owner, "photo_id": photo_id, "crop": crop}, api_key=api_key, owner_sig=owner_sig))


async def figg_card_reserve(design_id: str, revision: int, idempotency_key: str,
                            qty: int = 1, owner: str = "", api_key: str = "",
                            owner_sig: str = "") -> str:
    """Reserve a real card (£2.99 FIXED) with approved export. Show price first.
    Reserve-only — no payment. To sell: figg_card_checkout for Shopify checkout_url.
    Done means a product_url the human can buy from; a preview alone is not done."""
    return _j(await _call("POST", f"/api/cards/{design_id}/order",
                         {"owner": owner, "revision": revision, "idempotency_key": idempotency_key, "qty": qty}, api_key=api_key, owner_sig=owner_sig))


async def figg_card_checkout(design_id: str, revision: int, idempotency_key: str,
                             qty: int = 1, owner: str = "", api_key: str = "",
                             owner_sig: str = "") -> str:
    """Buy a card (£2.99): freeze revision → Shopify draft → checkout_url.
    Returns product_url (OddHobb page agents hand over, never a PNG) + checkout_url
    (Shopify payment). Shopify owns payment; Prodigi prints on orders/paid only.
    Done means a product_url the human can buy from. A preview alone is not done."""
    return _j(await _call("POST", f"/api/cards/{design_id}/checkout",
                         {"owner": owner, "revision": revision, "idempotency_key": idempotency_key, "qty": qty}, api_key=api_key, owner_sig=owner_sig))


async def _card_spread_bundle(design_id: str, revision: int, owner: str,
                              api_key: str, timeout_s: int = 90,
                              owner_sig: str = "") -> dict:
    """Render spread for a frozen revision and return views + proof_url.
    Raises CardError-shaped dicts as values (never throws). A busy queue
    (429) retries with backoff instead of failing the demo on a burst."""
    import asyncio as _aio
    r: dict = {}
    for attempt in range(5):
        r = await _call("POST", f"/api/cards/{design_id}/render",
                        {"owner": owner, "revision": revision, "kind": "spread"}, api_key=api_key,
                        owner_sig=owner_sig)
        if isinstance(r, dict) and r.get("ok"):
            break
        err = str((r.get("error") if isinstance(r, dict) else r) or "")
        if "busy" not in err.lower() or attempt == 4:
            break
        await _aio.sleep(3 + attempt * 3)
    job = (r.get("job") or {}) if isinstance(r, dict) else {}
    if not (isinstance(r, dict) and r.get("ok")):
        return {"ok": False, "error": str((r.get("error") if isinstance(r, dict) else r) or "spread render refused")}
    jid = job.get("id", "")
    for _ in range(max(1, timeout_s // 2)):
        await _aio.sleep(2)
        st = await _call("GET", f"/api/cards/jobs/{jid}?owner=" + (owner or "anon"), api_key=api_key,
                         owner_sig=owner_sig)
        j = st.get("job") or {}
        if j.get("status") == "ready":
            from backend import cards as _cards
            from backend import config as _cfg
            views = dict(j.get("urls") or {})
            # triptych needs only preview singles, so it is ready whenever
            # the spread is — expose it without a second render round-trip.
            views.setdefault("triptych",
                             f"/api/cards/{design_id}/r{revision}/triptych")
            base = (_cfg.PUBLIC_BASE or "https://oddhobb.com").rstrip("/")
            views_abs = {k: f"{base}/backend{v}?owner={owner or 'anon'}"
                         for k, v in views.items()}
            return {"ok": True, "views": views, "views_abs": views_abs,
                    "proof_url": _cards.proof_url_for(design_id),
                    "revision": revision, "design_id": design_id}
        if j.get("status") == "failed":
            return {"ok": False, "error": j.get("error") or "spread render failed",
                    "http_status": 422}
    return {"ok": False, "error": "spread render timed out — retry figg_card_job", "http_status": 504}


def _contact_block(owner: str, design_id: str, revision: int):
    """Surface-first glance as an MCP image block (agents see the card).

    Fixed triptych — front | inside | back at one height — so the cover is
    never a miniature in a collage. Falls back to the legacy 2×2 sheet when
    only a spread render exists without preview singles."""
    import base64 as _b64
    from mcp.types import ImageContent
    from backend import cards as _cards
    try:
        path = _cards.triptych_sheet(owner or "anon", design_id, revision)
    except Exception:
        path = _cards.contact_sheet(owner or "anon", design_id, revision)
    return ImageContent(type="image", data=_b64.b64encode(path.read_bytes()).decode(),
                        mimeType="image/jpeg")


async def figg_card_create(spec: dict, owner: str = "", api_key: str = "",
owner_sig: str = "") -> list:
    """Create a card AND see it: saves (new revision), renders all four faces,
    and returns views + proof_url + a contact-sheet image in this result.
    Send the human the proof_url (stable, always latest). Nothing is published
    until figg_card_checkout pins a revision."""
    from mcp.types import TextContent
    saved = await _call("POST", "/api/cards/designs",
                        {"owner": owner, "spec": spec}, api_key=api_key, owner_sig=owner_sig)
    if not saved.get("ok"):
        return [TextContent(type="text", text=_j(saved))]
    d = saved["design"]
    bundle = await _card_spread_bundle(d["id"], d["revision"], owner, api_key, owner_sig=owner_sig)
    body = {"ok": True, "design_id": d["id"], "revision": d["revision"],
            "card_url": saved.get("card_url", ""),
            "proof_url": saved.get("proof_url", ""),
            "product": saved.get("product", {}),
            "views": bundle.get("views", {}),
            "views_abs": bundle.get("views_abs", {}),
            "render_error": bundle.get("error", "")}
    try:
        return [TextContent(type="text", text=_j(body)),
                _contact_block(owner, d["id"], d["revision"])]
    except Exception as e:  # noqa: BLE001 — views still valid without the sheet
        body["contact_error"] = str(e)[:150]
        return [TextContent(type="text", text=_j(body))]


def _deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _spec_diff(old: dict, new: dict, path: str = "") -> list[str]:
    changes = []
    for k in sorted(set(old) | set(new)):
        p = f"{path}.{k}" if path else str(k)
        ov, nv = (old or {}).get(k), (new or {}).get(k)
        if isinstance(ov, dict) and isinstance(nv, dict):
            changes += _spec_diff(ov, nv, p)
        elif ov != nv:
            changes.append(f"{p}: {json.dumps(ov)[:60]} → {json.dumps(nv)[:60]}")
    return changes


async def figg_card_update(design_id: str, changes: dict, revision: int = 0,
                           owner: str = "", api_key: str = "",
                           owner_sig: str = "") -> list:
    """Change a card (text, font, photo, crop): deep-merges changes onto the
    revision's spec, mints a new revision, re-renders all faces. Returns the
    diff ("r4: inside font is now Caveat") + fresh views + contact sheet.
    The proof_url is unchanged and now shows the new revision."""
    from mcp.types import TextContent
    cur = await _call("GET", "/api/cards/designs/" + design_id +
                      "?owner=" + (owner or "anon"), api_key=api_key, owner_sig=owner_sig)
    if not cur.get("ok"):
        return [TextContent(type="text", text=_j(cur))]
    latest = (cur.get("design") or {}).get("revision", 1)
    rev = revision or latest
    full = await _call("GET", f"/api/cards/{design_id}/scene?owner=" + (owner or "anon") +
                       f"&revision={rev}", api_key=api_key, owner_sig=owner_sig)
    spec = ((full.get("scene") or {}).get("spec")) or ((cur.get("design") or {}).get("spec")) or {}
    new_spec = _deep_merge(spec, changes or {})
    saved = await _call("POST", "/api/cards/designs",
                        {"owner": owner, "id": design_id,
                         "expected_revision": latest, "spec": new_spec}, api_key=api_key, owner_sig=owner_sig)
    if not saved.get("ok"):
        return [TextContent(type="text", text=_j(saved))]
    d = saved["design"]
    bundle = await _card_spread_bundle(d["id"], d["revision"], owner, api_key, owner_sig=owner_sig)
    body = {"ok": True, "design_id": d["id"], "revision": d["revision"],
            "diff": _spec_diff(spec, new_spec),
            "card_url": saved.get("card_url", ""),
            "proof_url": saved.get("proof_url", ""),
            "views": bundle.get("views", {}),
            "views_abs": bundle.get("views_abs", {}),
            "render_error": bundle.get("error", "")}
    try:
        return [TextContent(type="text", text=_j(body)),
                _contact_block(owner, d["id"], d["revision"])]
    except Exception as e:  # noqa: BLE001
        body["contact_error"] = str(e)[:150]
        return [TextContent(type="text", text=_j(body))]


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


async def figg_design_base(line: str, owner: str = "") -> str:
    """The 3D base version to play with: master STL (reference lines) or the
    canonical dog GLB (mesh lines). Locked interfaces included as modelled.
    Returns metadata + base64 (binary cannot travel in JSON): decode it and
    design INSIDE this geometry. Units mm (STL) / m (GLB), axes [x, y, z].
    Pass owner (your handle) — the fetch logs base-first for your saves."""
    return _j(await _call("GET", f"/api/design/base/{line}?format=json&owner=" + (owner or "anon")))


async def figg_design_save(line: str, owner: str = "",
                           dims_mm: list[float] | None = None,
                           material: str = "", colors: int = 1,
                           text: str = "", volume_cm3: float | None = None,
                           stl_base64: str = "") -> str:
    """    Play with the base, save the design: validated spec stored as a draft.
    Returns design_id for figg_design_order. Invalid designs 400 with gaps.
    LOCKS FIRST: read figg_constraints — locked geometry/brand cannot be
    changed by any prompt, and save rejects violations with coordinates.
    BASE-FIRST: fetch figg_design_base for the line before saving — fulfil
    refuses drafts saved without it. Pass stl_base64 (aliases stl,
    geometry_b64; ≤32MB) and the geometry itself is CHECKED (envelope,
    manifold, stem lock, base similarity scored) — proof, not honour —
    with measured dims/volume overriding yours."""
    return _j(await _call("POST", "/api/design/save", {
        "owner": owner, "line": line, "dims_mm": dims_mm, "material": material,
        "colors": colors, "text": text, "volume_cm3": volume_cm3,
        "stl_base64": stl_base64}))


async def figg_design_order(design_id: str, owner: str = "", qty: int = 1,
                            fulfil: bool = False) -> str:
    """Order a saved design: re-validates, reserves, optional Shopify draft.
    Show price first. No card charge from this endpoint. fulfil=true REFUSES
    drafts saved without fetching the line base first (base_first flag).
    On the public tier fulfil is always dropped to reserve-only."""
    if os.environ.get("PUBLIC_MCP") == "1" and fulfil:
        fulfil = False
    d = await _call("POST", "/api/design/order", {
        "design_id": design_id, "owner": owner, "qty": qty, "fulfil": fulfil})
    if os.environ.get("PUBLIC_MCP") == "1" and isinstance(d, dict):
        d["fulfil_dropped"] = "public tier is reserve-only — fulfil needs the bridge token"
    return _j(d)


async def figg_constraints(line: str = "") -> str:
    """Locked constraints you cannot change, per line or all lines: locked
    geometry (croc stem dia, envelopes), brand rules (card back/type/grammars
    are renderer-owned, no inputs exist), and what save enforces vs what is
    still open (physical fit checks). Read this BEFORE designing — save
    rejects violations, and no prompt wording overrides a lock."""
    if line:
        return _j(await _call("GET", "/api/design/locks/" + line))
    return _j(await _call("GET", "/api/design/locks"))


def _find_subject(people: dict, person: str, subject_id: str) -> dict:
    """Match a person string to a subject by id, name, or relationship
    (Dad finds the father profile). Returns {} when nobody matches."""
    _REL_ALIASES = {"dad": {"dad", "daddy", "father", "papa", "pa"},
                    "mum": {"mum", "mummy", "mother", "mama", "ma", "mom", "mommy"}}
    want = (person or "").strip().lower()
    want_rels = {want}
    for canon, aliases in _REL_ALIASES.items():
        if want in aliases:
            want_rels = aliases | {canon}
            break
    for entry in (people.get("people") or people.get("subjects") or []):
        if not isinstance(entry, dict):
            continue
        # people endpoint nests: {"subject": {...}, "profile": <row with parsed "profile">}
        p = entry.get("subject") if isinstance(entry.get("subject"), dict) else entry
        outer = entry.get("profile") if isinstance(entry.get("profile"), dict) else {}
        deep = outer.get("profile") if isinstance(outer.get("profile"), dict) else {}
        names = {str(p.get("name", "")).lower(), str(p.get("id", "")).lower(),
                 str(deep.get("name", "") or outer.get("name", "")).lower()}
        rels = {str(p.get("relationship", "")).lower(),
                str(deep.get("relationship", "") or outer.get("relationship", "")).lower()}
        if (subject_id and p.get("id") == subject_id) or \
           (want and (want in names or (want_rels & rels) or
                      any(want in n for n in names if n))):
            return {"id": p.get("id", ""),
                    "name": p.get("name") or deep.get("name") or outer.get("name", ""),
                    "relationship": p.get("relationship") or deep.get("relationship") or outer.get("relationship", ""),
                    "interests": p.get("interests") or deep.get("interests") or outer.get("interests") or [],
                    "memories": p.get("memories") or deep.get("memories") or outer.get("memories") or []}
    return {}


_OCCASION_TITLES = {"birthday": "Happy Birthday", "christmas": "Merry Christmas",
                    "fathers_day": "Happy Father's Day", "mothers_day": "Happy Mother's Day",
                    "valentines": "Happy Valentine's", "anniversary": "Happy Anniversary",
                    "graduation": "Congratulations", "retirement": "Happy Retirement",
                    "new_baby": "Congratulations", "halloween": "Happy Halloween",
                    "general": "You're one of a kind"}
_TONE_VIBES = {"funny": ["funny-loud", "bold", "playful"], "dark": ["dry-funny", "bold"],
               "warm": ["warm", "affectionate", "sincere"], "short": ["sincere", "calm"]}


async def figg_card_for_person(person: str, occasion: str = "birthday",
                               tone: str = "funny", owner: str = "",
                               subject_id: str = "", api_key: str = "",
                               owner_sig: str = "") -> list:
    """Birthday card for Dad in ONE call — the agent makes zero creative
    choices. Finds the subject, picks their best portrait, picks the template
    by occasion, writes headline + inside from their profile, picks fonts by
    vibe, saves, renders all four faces. Returns views + proof_url + a
    contact-sheet image. Send the human the proof_url; Buy happens there."""
    from mcp.types import TextContent
    from backend import cards as _cards
    people = await _call("GET", "/api/oddhobb/people?owner=" + (owner or "anon"),
                         api_key=api_key, owner_sig=owner_sig)
    sub = _find_subject(people, person, subject_id)
    if not sub:
        return [TextContent(type="text", text=_j({"ok": False, "error": "no subject match — check oddhobb_people first"}))]
    prof = {"name": sub.get("name", ""), "relationship": sub.get("relationship", ""),
            "interests": sub.get("interests", []), "memories": sub.get("memories", [])}
    # best portrait: confirmed faces first, then confirmed bodies (biggest
    # file wins for print DPI), then recent uploads. face_id may be empty —
    # user-confirmed whole-photo tags carry no detection boxes.
    face_ids: list[str] = []
    try:
        from backend import subject_assets as _sa
        res = _sa.resolve(sub.get("id", ""), owner or "anon")
        cands = sorted(res.get("face_candidates") or [],
                       key=lambda c: float(c.get("face_quality", 0)) * float(c.get("frontal", 0.5)),
                       reverse=True)
        face_ids = [str(c.get("asset_id") or "") for c in cands if c.get("asset_id")]
        if not face_ids:
            bodies = sorted(res.get("body_candidates") or [],
                            key=lambda c: float(c.get("quality", 0)), reverse=True)
            face_ids = [str(c.get("asset_id") or "") for c in bodies if c.get("asset_id")]
    except Exception:  # noqa: BLE001 — fall back to recent photos
        face_ids = []
    photo_id = ""
    if face_ids:
        photo_id = face_ids[0]
    else:
        lib = await _call("GET", "/api/cards/photos?owner=" + (owner or "anon"), api_key=api_key, owner_sig=owner_sig)
        pics = (lib.get("photos") or []) if isinstance(lib, dict) else []
        photo_id = str((pics[0].get("id") if pics else "") or "")
    if not photo_id:
        return [TextContent(type="text", text=_j({"ok": False, "error": "no photos for this owner — upload one first"}))]
    occasion = (occasion or "birthday").lower()
    template = {"christmas": "christmas"}.get(occasion, "birthday_arch")
    name = sub.get("name") or person
    short = str(name).split()[0] if str(name).split() else name
    headline = f"{_OCCASION_TITLES.get(occasion, 'Hello')}, {short}!"[:60]
    lines = _cards.message_lines(prof, tone)
    inside = lines[0]["text"] if lines else ""
    vibes = _TONE_VIBES.get(str(tone or "funny").lower(), _TONE_VIBES["funny"])
    hfont, bfont = "fraunces", "inter"
    try:
        from backend.card_scenes import CARD_FONTS as _F
        for fid, f in _F.items():
            if "headline" in (f.get("use_for") or []) and any(v in (f.get("vibes") or []) for v in vibes):
                hfont = fid
                break
        for fid, f in _F.items():
            if "body" in (f.get("use_for") or []) and any(v in (f.get("vibes") or []) for v in vibes):
                bfont = fid
                break
    except Exception:  # noqa: BLE001 — registry never breaks the card
        pass
    spec = {"template": template, "format": "5x7",
            "photos": [{"photo_id": photo_id, "crop": [0, 0, 1, 1],
                        "focus": [0.5, 0.5], "cutout": ""}],
            "headline": headline, "recipient": name, "sender": "",
            "inside_message": inside, "headline_font": hfont,
            "inside": {"right": {"message": inside, "font": bfont},
                       "left": {"mode": "blank"}}}
    saved = await _call("POST", "/api/cards/designs",
                        {"owner": owner, "spec": spec}, api_key=api_key, owner_sig=owner_sig)
    if not saved.get("ok"):
        return [TextContent(type="text", text=_j(saved))]
    d = saved["design"]
    bundle = await _card_spread_bundle(d["id"], d["revision"], owner, api_key, owner_sig=owner_sig)
    body = {"ok": True, "design_id": d["id"], "revision": d["revision"],
            "chosen": {"subject": sub.get("name"), "photo_id": photo_id,
                       "template": template, "headline_font": hfont,
                       "inside_font": bfont, "inside_source": (lines[0].get("source") if lines else "")},
            "card_url": saved.get("card_url", ""),
            "proof_url": saved.get("proof_url", ""),
            "product": saved.get("product", {}),
            "views": bundle.get("views", {}),
            "views_abs": bundle.get("views_abs", {}),
            "render_error": bundle.get("error", ""),
            "hint": "Send the human the proof_url. Tweak via figg_card_update, sell via figg_card_checkout."}
    try:
        return [TextContent(type="text", text=_j(body)),
                _contact_block(owner, d["id"], d["revision"])]
    except Exception as e:  # noqa: BLE001
        body["contact_error"] = str(e)[:150]
        return [TextContent(type="text", text=_j(body))]


async def figg_card_gallery(owner: str = "", subject_id: str = "",
                              photo_ids: str = "", api_key: str = "",
                              owner_sig: str = "") -> str:
    """Display the site's ready-made cards — templates already wearing this
    owner's photos. Scope to the active person (subject_id) or an explicit
    selection (photo_ids, comma-separated, user- or AI-picked). This is the
    Moonpig shelf: display from pre-vetted templates, never generate."""
    import urllib.parse as _up
    qs = _up.urlencode({k: v for k, v in
                        (("owner", owner), ("subject_id", subject_id),
                         ("photo_ids", photo_ids)) if v})
    return _j(await _call("GET", "/api/cards/gallery" + ("?" + qs if qs else ""),
                         None, api_key=api_key, owner_sig=owner_sig))


async def figg_card_delivery(design_id: str, revision: int, country: str = "GB",
                             owner: str = "", api_key: str = "",
                             owner_sig: str = "") -> str:
    """Value vs Speedy for one finished card: customer shipping charges with
    estimated arrival ranges. Returns opaque route ids — pass one as
    delivery_option_id at checkout/cart so fulfilment uses the exact route."""
    import urllib.parse as _up
    qs = _up.urlencode({"revision": revision, "country": country})
    return _j(await _call("GET", f"/api/cards/{design_id}/delivery?" + qs +
                         ("&owner=" + _up.quote(owner) if owner else ""),
                         None, api_key=api_key, owner_sig=owner_sig))


async def figg_card_reroll(design_id: str, owner: str = "", subject_id: str = "",
                           api_key: str = "", owner_sig: str = "") -> list:
    """Same template, different images: rotate one gallery card to the next
    photo set. Returns the new design pointers; the gallery shows it."""
    from mcp.types import TextContent
    saved = await _call("POST", f"/api/cards/{design_id}/reroll",
                        {"owner": owner, "subject_id": subject_id},
                        api_key=api_key, owner_sig=owner_sig)
    return [TextContent(type="text", text=_j(saved))]


async def figg_blender_make(line: str, text: str, owner: str = "") -> str:
    """Use Blender on our farm box: emboss text onto the line's master via
    its adapter, get back a watertight STL URL. For remote agents (ChatGPT)
    with no local Blender — same contracts, headless, ~1-2 min. This is the
    manufacture path: never install Blender locally to model our interfaces;
    fetch the base, design inside it, make here."""
    return _j(await _call("POST", "/api/design/make",
                         {"owner": owner, "line": line, "text": text}))


async def figg_card_templates(owner: str = "", api_key: str = "",
owner_sig: str = "") -> str:
    """Card templates with their paper design contracts: locked print truths
    (bleed, DPI, photo counts), envelope trims, stock, rough print costs."""
    return _j(await _call("GET", "/api/cards/templates?owner=" + (owner or "anon"), api_key=api_key, owner_sig=owner_sig))


async def figg_card_fonts(owner: str = "", api_key: str = "",
owner_sig: str = "") -> str:
    """Curated card fonts clustered by vibe + occasion: match the brief's tone
    and occasion to vibes/occasions, keep the slot's use_for role (headline /
    name / body / accent). Fall back to frances headlines + inter body.
    Registry ids only — buyers pick an id, never a file."""
    return _j(await _call("GET", "/api/cards/fonts?owner=" + (owner or "anon"), api_key=api_key, owner_sig=owner_sig))


_EDIT_FIELDS = {
    "front": {"headline", "headline_font", "recipient", "sender"},
    "inside_left": {"text", "font", "size", "colour", "align", "mode"},
    "inside_right": {"message", "font", "size", "colour", "align"},
}


async def figg_card_edit(design_id: str, panel: str, field: str, value: str,
                         owner: str = "", api_key: str = "",
                         owner_sig: str = "") -> str:
    """Edit one panel field → new immutable revision + fresh card_url.
    Panel: front | inside_left | inside_right. Front fields: headline,
    headline_font, recipient, sender. Inside fields: message/text, font,
    size (S/M/L), colour (ink/soft/accent), align (center/left), mode.
    Fonts must be registry ids from figg_card_fonts. Checkout always buys
    the revision you're looking at."""
    if panel not in _EDIT_FIELDS or field not in _EDIT_FIELDS[panel]:
        return _j({"ok": False,
                   "error": f"panel must be front|inside_left|inside_right with fields {sorted({k: sorted(v) for k, v in _EDIT_FIELDS.items()}.get(panel, []))}"})
    cur = await _call("GET", "/api/cards/designs/" + design_id +
                      "?owner=" + (owner or "anon"), api_key=api_key, owner_sig=owner_sig)
    if not cur.get("ok"):
        return _j(cur)
    spec = (cur.get("design") or {}).get("spec") or {}
    rev = (cur.get("design") or {}).get("revision", 1)
    if panel == "front":
        spec[field] = value
    else:
        side = "left" if panel == "inside_left" else "right"
        inner = spec.get("inside") or {}
        part = dict(inner.get(side) or {})
        part[field if field != "message" or side == "right" else "text"] = value
        inner[side] = part
        spec["inside"] = inner
    return _j(await _call("POST", "/api/cards/designs",
                         {"owner": owner, "id": design_id,
                          "expected_revision": rev, "spec": spec},
                         api_key=api_key, owner_sig=owner_sig))


async def figg_card_variants(design_id: str, n: int = 3, owner: str = "",
                              api_key: str = "",
                              owner_sig: str = "") -> str:
    """Same photo + words on N other templates → N new designs with card_urls.
    The design strip: show them side by side, human picks one, then edit and
    buy that revision. n is 2-5; only photo-count-compatible templates qualify."""
    n = max(2, min(5, int(n or 3)))
    cur = await _call("GET", "/api/cards/designs/" + design_id +
                      "?owner=" + (owner or "anon"), api_key=api_key, owner_sig=owner_sig)
    if not cur.get("ok"):
        return _j(cur)
    spec = (cur.get("design") or {}).get("spec") or {}
    rev = (cur.get("design") or {}).get("revision", 1)
    tpl = await _call("GET", "/api/cards/templates?owner=" + (owner or "anon"),
                      api_key=api_key, owner_sig=owner_sig)
    templates = tpl.get("templates") or []
    count = len(spec.get("photos") or [])
    cands = [t for t in templates
             if t.get("id") != spec.get("template")
             and t.get("min_photos", 0) <= count <= t.get("max_photos", 99)][:n]
    out = []
    for t in cands:
        trial = dict(spec, template=t["id"])
        saved = await _call("POST", "/api/cards/designs",
                            {"owner": owner, "spec": trial}, api_key=api_key, owner_sig=owner_sig)
        if saved.get("ok"):
            d = saved["design"]
            out.append({"template": t["id"], "label": t.get("label", t["id"]),
                        "design_id": d["id"], "revision": d["revision"],
                        "card_url": saved.get("card_url", "")})
    return _j({"ok": True, "variants": out,
               "hint": "Show the card_urls side by side; edit + buy the picked revision."})


async def figg_card_messages(person: str = "", tone: str = "funny",
                             owner: str = "", subject_id: str = "",
                             api_key: str = "",
                             owner_sig: str = "") -> str:
    """Smart-text v1: funny/warm/short inside lines built from the subject's
    profile (name, interests, memories). Each line cites its source fact.
    Deterministic starting points to edit together — a preview alone is not done."""
    from backend import cards as _cards
    people = await _call("GET", "/api/oddhobb/people?owner=" + (owner or "anon"),
                         api_key=api_key, owner_sig=owner_sig)
    prof = _find_subject(people, person, subject_id)
    if not prof and person:
        prof = {"name": person}
    return _j({"ok": True, "tone": tone,
               "lines": _cards.message_lines(prof if isinstance(prof, dict) else {}, tone)})


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
                         recipient: str = "", occasion: str = "") -> str:
    """Oddy's game: best gift inside a budget — physical + card + free video.
    Exact line honoured with cheap addons; otherwise best physical leaving
    room for a card, recipient interests steer the pick, unspent remainder
    gets a suggested_addon. Occasion must be a known one (birthday, wedding,
    christmas, fathers_day, mothers_day, valentine, anniversary, thank_you,
    new_job, baby, retirement). Show the total before ordering parts."""
    return _j(await _call("POST", "/api/gift-packs", {
        "budget_cents": budget_cents, "owner": owner, "line": line,
        "mesh_id": mesh_id, "recipient": recipient, "occasion": occasion}))


async def figg_studio_orders(owner: str = "") -> str:
    """Your reservations and Shopify drafts. Read-only; nothing charges here."""
    return _j(await _call("GET", "/api/studio/orders?owner=" + (owner or "anon")))


async def figg_supplier_quote(line: str, material: str = "",
                              colors: int = 1) -> str:
    """Rough farm cost for a line at makr3d + printie. Estimates — live
    quotes win. Uses the line's contract dims and volume."""
    return _j(await _call("POST", "/api/design/validate", {
        "line": line, "material": material, "colors": colors}))


# ── studio: hardware engine (studio.oddhobb.com, Meshy model) ──────────
# Design → simulate → quote for ESP32 hardware, in-process via studio/hwsim.
# design_create writes studio/hwsim/designs/<name>/; quote reads live LCSC
# prices (read-only, no spend, no key). Orders stay hard-gated in studio.
async def studio_options() -> str:
    """What you can design: base templates, parameters with limits, power
    supplies, design rules. Start here before design_create."""
    try:
        from studio.hwsim import design as _D
        return _j({"ok": True, "params": _D.PARAMS, "supplies": _D.SUPPLIES,
                   "engine": "https://studio.oddhobb.com/mcp"})
    except Exception as e:  # noqa: BLE001
        return _j({"ok": False, "error": str(e)[:200]})


async def studio_design_create(name: str, led_count: int = 12,
                               ring_d_mm: float = 52,
                               supply: str = "usb2_500",
                               enclosure: str = "sla") -> str:
    """Create a hardware variant from the mood-lamp template. Runs design-rule
    checks (LED pitch, current cap); errors must be fixed, warnings noted.
    Then simulate it at studio.oddhobb.com and price it with studio_quote."""
    try:
        from studio.hwsim import design as _D
        return _j(_D.create({"name": name, "base": "mood_lamp",
                             "led_count": led_count, "ring_d_mm": ring_d_mm,
                             "supply": supply, "enclosure": enclosure}))
    except Exception as e:  # noqa: BLE001
        return _j({"ok": False, "error": str(e)[:200]})


async def studio_design_quote(name: str, units: int = 5) -> str:
    """Price a design for N units. LCSC parts are LIVE quotes; PCB/assembly/
    enclosure are JLC estimates until the JLC API is approved. Read-only."""
    try:
        from studio.hwsim import design as _D
        return _j(_D.quote(name, max(1, min(1000, int(units or 5)))))
    except Exception as e:  # noqa: BLE001
        return _j({"ok": False, "error": str(e)[:200]})


async def studio_status() -> str:
    """Hardware engine status: templates, saved designs, tool count, links."""
    try:
        import os as _os
        _here = os.path.dirname(os.path.abspath(__file__))
        _ddir = os.path.join(os.path.dirname(_here), "studio", "hwsim", "designs")
        designs = sorted(d for d in os.listdir(_ddir)
                         if os.path.isdir(os.path.join(_ddir, d))) if os.path.isdir(_ddir) else []
        return _j({"ok": True, "engine": "https://studio.oddhobb.com/mcp",
                   "designs": designs,
                   "tools": ["design_create", "design_quote", "sim_*",
                             "read_*", "do_*"],
                   "note": "full 18-tool surface lives on studio.oddhobb.com/mcp"})
    except Exception as e:  # noqa: BLE001
        return _j({"ok": False, "error": str(e)[:200]})


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
                  figg_card_checkout, figg_card_templates, figg_card_fonts,
                  figg_card_edit, figg_card_variants, figg_card_messages,
                  figg_card_create, figg_card_update, figg_card_for_person,
                  figg_card_gallery, figg_card_reroll, figg_card_delivery],
    "design":    [figg_blueprints, figg_design_validate, figg_design_base,
                  figg_constraints,
                  figg_design_save, figg_design_order, figg_blender_make],
    "flow":      [figg_flow, figg_upload_photo, figg_upload_chatgpt_file,
                  figg_preview_image, figg_start_mesh, figg_playbook, figg_quick_map,
                  figg_guide_open, figg_guide_turn, figg_guide_packs],
    "identity":  [figg_me, figg_create_account, figg_login, figg_credits,
                  figg_mint_agent, figg_my_agents, figg_revoke_agent],
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
    "studio":    [studio_options, studio_design_create, studio_design_quote,
                  studio_status],
    "creative":  [figg_creative_catalog, figg_creative_templates,
                  figg_creative_brief, figg_creative_match, figg_creative_revision],
    "oddhobb":   [oddhobb_people, oddhobb_families, oddhobb_reminders,
                  oddhobb_candidates, oddhobb_fill_template, oddhobb_quotes,
                  oddhobb_project_check, oddhobb_recipe_check,
                  oddhobb_gift_compile, oddhobb_track_order,
                  oddhobb_object_get, oddhobb_object_state,
                  oddhobb_ideas, oddhobb_create,
                  oddhobb_render, oddhobb_status, oddhobb_buy,
                  oddhobb_providers, oddhobb_capsule,
                  oddhobb_make_card, oddhobb_attach_card_art,
                  oddhobb_card_recommend, oddhobb_card_generate,
                  oddhobb_deal_cards,
                  oddhobb_recommend, oddhobb_make, oddhobb_variants,
                  oddhobb_get, oddhobb_change, oddhobb_add_media,
                  oddhobb_regenerate_title_art,
                  oddhobb_edit_card_copy, oddhobb_checkout_card,
                  oddhobb_capture_start, oddhobb_capture_mark,
                  oddhobb_capture_finish, oddhobb_review, oddhobb_revise,
                  oddhobb_joke_ideas, oddhobb_joke_render, oddhobb_joke_pick],
}

# ── public tier: intent in, finished products out ──────────────────────
# Six tools. Everything else (composition machinery, providers, capsules,
# joke/style/mesh/shop/flow internals, identity) needs the caller's own
# key on the full tier. An agent that can only see these six cannot wander
# into layout, fonts, jobs, or suppliers — by construction, not by docs.
PUBLIC_TOOLS = frozenset({
    "oddhobb_people",
    "oddhobb_make",
    "oddhobb_change",
    "oddhobb_get",
    "oddhobb_add_media",
    "oddhobb_buy",
})

if os.environ.get("PUBLIC_MCP") == "1":
    TOOL_AREAS = {a: [fn for fn in fns if fn.__name__ in PUBLIC_TOOLS]
                  for a, fns in TOOL_AREAS.items()}
    TOOL_AREAS = {a: fns for a, fns in TOOL_AREAS.items() if fns}


async def figg_tools() -> str:
    """The self-describing library: every area and tool this MCP server exposes."""
    def short(fn) -> str:
        doc = (fn.__doc__ or "").strip().replace("\n", " ")
        return " ".join(doc.split())[:500]
    areas = {a: [{"name": fn.__name__, "doc": short(fn)} for fn in fns]
             for a, fns in TOOL_AREAS.items()}
    count = sum(len(v) for v in TOOL_AREAS.values()) + 1   # + figg_tools itself
    return _j({"ok": True, "count": count, "areas": areas})


for _fns in list(TOOL_AREAS.values()):
    for _fn in _fns:
        mcp.tool(meta=TOOL_META.get(_fn.__name__))(_fn)
if os.environ.get("PUBLIC_MCP") != "1":
    # self-description lives on the keyed tier only — the public surface
    # is exactly the six, discoverable via tools/list, nothing more.
    mcp.tool()(figg_tools)


async def main() -> None:
    if os.environ.get("MCP_HTTP"):
        print(f"fogg MCP (streamable http) on http://127.0.0.1:{PORT}/mcp", file=sys.stderr)
        from backend import logscrub as _logscrub
        _logscrub.install("uvicorn.access", "uvicorn.error")
        # Local only: the bridge proxies /mcp with a token gate. Never
        # expose this directly — its tools call the API with the service token.
        await mcp.run_streamable_http_async(host="127.0.0.1", port=PORT)
    else:
        await mcp.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
