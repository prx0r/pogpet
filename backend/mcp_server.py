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


async def figg_start_mesh(photo_id: str, owner: str = "", single: bool = False) -> str:
    """Start sculpting an uploaded photo (photo_id from figg_upload_photo) -> returns the mesh job.

    Pass `owner` when acting for a known handle — without FIGG_OWNER/API key
    matching that owner the backend refuses non-anon credit burns.
    Sculpts want 3 angles of the same person (auto multi-image build, same 1
    credit); fewer needs explicit single=true. Provider failures refund.
    """
    payload = {"photo_id": photo_id, "single": single}
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


async def oddhobb_buy(creative_id: str='', revision: int=1, owner: str='', product: str='greeting_card', qty: int=1, api_key: str='') -> str:
    """Reserve a QC-passed revision. No card charge from this endpoint."""
    return _j(await _call('POST', '/api/oddhobb/buy', {'creative_id': creative_id, 'revision': revision, 'owner': owner, 'product': product, 'qty': qty}, api_key=api_key))


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
                            owner_sig: str = "") -> list:
    """Make a canonical birthday card in ONE call. Resolves the 4 best photos,
    writes bounded copy from the profile (or your hint), saves revision 1,
    renders front/inside/back/4-up + print PDF. Returns previews, proof_url,
    and a contact sheet. The agent supplies photos-by-choice + words only."""
    from mcp.types import TextContent
    from backend import cards as _cards
    if not signature.strip():
        return [TextContent(type="text", text=_j({"ok": False, "error": "signature required \u2014 ask the human who signs the card (never default to the recipient)"}))]
    people = await _call("GET", "/api/oddhobb/people?owner=" + (owner or "anon"),
                         api_key=api_key, owner_sig=owner_sig)
    sub = _find_subject(people, "", subject_id)
    if not sub:
        return [TextContent(type="text", text=_j({"ok": False, "error": "unknown subject — check oddhobb_people first"}))]
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
            if len(pids) == 4:
                break
    except Exception:  # noqa: BLE001
        pids = []
    if len(pids) < 4:
        return [TextContent(type="text", text=_j({"ok": False, "error": f"need 4 photos — only {len(pids)} confirmed"}) )]
    name = sub.get("name") or "them"
    short = str(name).split()[0] if str(name).split() else name
    title = f"Happy Birthday, {short}!"[:40]
    lines = _cards.message_lines(prof, tone)
    message = (message_hint.strip()[:240] if message_hint.strip()
               else (lines[0]["text"][:240] if lines else ""))
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
    bundle = await _card_spread_bundle(d["id"], d["revision"], owner, api_key, owner_sig=owner_sig)
    exp = await _call("POST", f"/api/cards/{d['id']}/render",
                      {"owner": owner, "revision": d["revision"], "kind": "export"}, api_key=api_key, owner_sig=owner_sig)
    body = {"ok": True, "design_id": d["id"], "revision": d["revision"],
            "template_id": "birthday_4photo",
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
        r2key = f"tmp/title-{design_id}-r{rev}.png"
        tmp, _ = _url.urlretrieve(imgs[0]["url"])
        from pathlib import Path as _P
        from backend import r2presign as _r2
        rk = _r2.put_temp(_P(tmp))
        try:
            from PIL import Image as _I
            _I.open(_P(tmp)).convert("RGBA").save(_P(tmp), "PNG")
            _cards.storage.put(_P(tmp), f"owners/{_cards.storage._slug(owner or 'anon')}/cards/{design_id}/title-art.png")
        finally:
            _r2.delete(rk)
        _fal.log_spend(owner=owner or "anon", adapter="fal.title_art",
                       endpoint="fal-ai/flux/dev", est_cost_usd=0.025, request_id=rid)
        key = f"owners/{_cards.storage._slug(owner or 'anon')}/cards/{design_id}/title-art.png"
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
    revision. Empty fields keep their current values."""
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
    return _j(await _call("POST", "/api/cards/designs",
                         {"owner": owner, "id": design_id,
                          "expected_revision": d.get("revision", 1), "spec": spec}, api_key=api_key, owner_sig=owner_sig))


async def oddhobb_checkout_card(design_id: str, revision: int, owner: str = "",
                                qty: int = 1, idempotency_key: str = "",
                                api_key: str = "",
                                owner_sig: str = "") -> str:
    """Pin a canonical revision and buy it (£7.99 → Shopify draft). 409s when
    that revision has no passing export render — render first, then pay."""
    return _j(await _call("POST", f"/api/cards/{design_id}/checkout",
                         {"owner": owner, "revision": revision, "qty": qty,
                          "idempotency_key": idempotency_key or f"canonical-{design_id}-r{revision}"}, api_key=api_key, owner_sig=owner_sig))


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
    """Reserve a real card (£7.99 FIXED) with approved export. Show price first.
    Reserve-only — no payment. To sell: figg_card_checkout for Shopify checkout_url.
    Done means a product_url the human can buy from; a preview alone is not done."""
    return _j(await _call("POST", f"/api/cards/{design_id}/order",
                         {"owner": owner, "revision": revision, "idempotency_key": idempotency_key, "qty": qty}, api_key=api_key, owner_sig=owner_sig))


async def figg_card_checkout(design_id: str, revision: int, idempotency_key: str,
                             qty: int = 1, owner: str = "", api_key: str = "",
                             owner_sig: str = "") -> str:
    """Buy a card (£7.99): freeze revision → Shopify draft → checkout_url.
    Returns product_url (OddHobb page agents hand over, never a PNG) + checkout_url
    (Shopify payment). Shopify owns payment; Prodigi prints on orders/paid only.
    Done means a product_url the human can buy from. A preview alone is not done."""
    return _j(await _call("POST", f"/api/cards/{design_id}/checkout",
                         {"owner": owner, "revision": revision, "idempotency_key": idempotency_key, "qty": qty}, api_key=api_key, owner_sig=owner_sig))


async def _card_spread_bundle(design_id: str, revision: int, owner: str,
                              api_key: str, timeout_s: int = 90,
                              owner_sig: str = "") -> dict:
    """Render spread for a frozen revision and return views + proof_url.
    Raises CardError-shaped dicts as values (never throws)."""
    import asyncio as _aio
    r = await _call("POST", f"/api/cards/{design_id}/render",
                    {"owner": owner, "revision": revision, "kind": "spread"}, api_key=api_key,
                    owner_sig=owner_sig)
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
            views = j.get("urls") or {}
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
    """2×2 contact-sheet JPEG as an MCP image block (agents see the card)."""
    import base64 as _b64
    from mcp.types import ImageContent
    from backend import cards as _cards
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
                  figg_card_create, figg_card_update, figg_card_for_person],
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
    "creative":  [figg_creative_catalog, figg_creative_templates,
                  figg_creative_brief, figg_creative_match, figg_creative_revision],
    "oddhobb":   [oddhobb_people, oddhobb_ideas, oddhobb_create,
                  oddhobb_render, oddhobb_status, oddhobb_buy,
                  oddhobb_providers, oddhobb_capsule,
                  oddhobb_make_card, oddhobb_regenerate_title_art,
                  oddhobb_edit_card_copy, oddhobb_checkout_card,
                  oddhobb_capture_start, oddhobb_capture_mark,
                  oddhobb_capture_finish, oddhobb_review, oddhobb_revise,
                  oddhobb_joke_ideas, oddhobb_joke_render, oddhobb_joke_pick],
}

# ── public tier: any agent, no token ─────────────────────────────────────
# Names here are the ONLY tools registered when PUBLIC_MCP=1. Reads plus
# self-serve identity (create account → own API key → keyed writes over REST
# or the gated MCP). Anything that spends (Meshy, video credits, our LLM key,
# Blender CPU, orders) stays on the token-gated server.
PUBLIC_TOOLS = frozenset({
    "figg_tools",
    "figg_create_account", "figg_login",
    "figg_catalog", "figg_products", "figg_concepts", "figg_quote",
    "figg_check_sku", "figg_product_assets", "figg_studio_props",
    "figg_studio_combos", "figg_product_personalise", "figg_gift_pack",
    "figg_supplier_quote",
    "figg_blueprints", "figg_design_validate", "figg_design_base",
    "figg_constraints",
    "figg_design_save", "figg_design_order",
    "figg_flow", "figg_playbook", "figg_quick_map",
    "figg_card_library", "figg_card_templates",
    "figg_card_save", "figg_card_render", "figg_card_scene", "figg_card_job",
    "figg_card_fonts", "figg_card_messages",
    "figg_card_create", "figg_card_update", "figg_card_for_person",
    "figg_mesh_status", "figg_measure",
    "figg_styles", "figg_install_style",
    "figg_acts", "figg_rooms",
    "figg_companygraph",
    "figg_creative_catalog", "figg_creative_templates", "figg_creative_brief",
    "figg_creative_match", "figg_creative_revision",
    "oddhobb_people", "oddhobb_ideas", "oddhobb_create",
    "oddhobb_render", "oddhobb_status", "oddhobb_buy",
    "oddhobb_providers", "oddhobb_capsule",
    "oddhobb_make_card", "oddhobb_edit_card_copy",
    "oddhobb_review", "oddhobb_revise",
    "oddhobb_joke_ideas", "oddhobb_joke_pick",
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
