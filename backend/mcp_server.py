"""figgsite MCP server — the platform, callable by an agent.

This is the "Muse agent drives everything" endgame in one file: ChatGPT, Grok,
Meta Muse or any MCP client connects, and gets the same verbs a human clicks.

    python3 -m backend.mcp_server     # stdio  (for local/agent harnesses)
    MCP_HTTP=1 python3 -m backend.mcp_server  # streamable HTTP on :8799/mcp

Identity: tools act as whoever's key is in `FIGG_API_KEY` (put your own in
.env). A separate agent credential minted via `POST /api/agents` can be used
instead — it keeps its own profile and only the permissions you granted.

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
    "fogg/pog.pet storefront API: pets become meshes, meshes become products, "
    "meshes perform. Prices are LIVE when a Prodigi SKU is attached, otherwise "
    "EST. Free tier: 3 sculpts and 5 videos per owner per day."
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

@mcp.tool()
async def figg_me() -> str:
    """Your profile: handle, active pog, roster and today's free credits."""
    return _j(await _call("GET", "/api/accounts/me"))


@mcp.tool()
async def figg_create_account(handle: str, password: str = "",
                              display_name: str = "") -> str:
    """Create an account. `handle` becomes the owner of everything it makes.
    Returns an api_key shown once — store it."""
    return _j(await _call("POST", "/api/accounts",
                          {"handle": handle, "password": password,
                           "display_name": display_name}))


@mcp.tool()
async def figg_login(handle: str, password: str) -> str:
    """Sign in with handle + password. Returns the api_key for this session."""
    return _j(await _call("POST", "/api/accounts/login",
                          {"handle": handle, "password": password}))


# ── meshes ──────────────────────────────────────────────────────────

@mcp.tool()
async def figg_styles() -> str:
    """Ready-made characters to start from. No Meshy key required — a pet
    that looks like *yours* still needs photo-to-3D, but everything downstream
    of the mesh is free."""
    return _j(await _call("GET", "/api/styles"))


@mcp.tool()
async def figg_install_style(style: str, owner: str = "") -> str:
    """Instantly install a style preset as an active pog (renders a portrait,
    stores it, binds all products). `style` is an id from figg_styles()."""
    return _j(await _call("POST", "/api/meshes/style",
                          {"style": style, "owner": owner}))


@mcp.tool()
async def figg_mesh_status(mesh_id: str, owner: str = "") -> str:
    """Status of one mesh plus every product it is active in."""
    q = f"?owner={owner}" if owner else ""
    return _j(await _call("GET", f"/api/meshes/{mesh_id}{q}"))


@mcp.tool()
async def figg_measure(mesh_id: str) -> str:
    """Geometry of a mesh: bounding box and print dimensions in mm."""
    return _j(await _call("GET", f"/api/meshes/{mesh_id}/measure"))


@mcp.tool()
async def figg_print_export(mesh_id: str, format: str = "stl",
                             height_mm: float = 0) -> str:
    """Export a printable file. format is 'stl' or 'obj'; height_mm scales the
    model to that print height (0 = leave native size). Returns a URL."""
    return _j(await _call("GET",
                          f"/api/meshes/{mesh_id}/print?format={format}&height_mm={height_mm}"))


# ── shop ────────────────────────────────────────────────────────────

@mcp.tool()
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


@mcp.tool()
async def figg_concepts() -> str:
    """The 36-concept template library: wizard / mystic / christmas ×
    solo / couple / solo_pet / pet, each with art direction."""
    return _j(await _call("GET", "/api/concepts"))


@mcp.tool()
async def figg_quote(sku: str, country: str = "GB", attrs: str = "{}") -> str:
    """Live Prodigi price for a SKU (item, shipping, tax, carrier)."""
    return _j(await _call("GET",
                          f"/api/prodigi/quote?sku={sku}&country={country}&attrs={attrs}"))


@mcp.tool()
async def figg_check_sku(sku: str) -> str:
    """Does this Prodigi SKU exist, and what attributes does quoting need?"""
    return _j(await _call("GET", f"/api/prodigi/check?sku={sku}"))


# ── perform ─────────────────────────────────────────────────────────

@mcp.tool()
async def figg_acts() -> str:
    """The talent-show roster (19 acts) and the three talents:
    comedy, dance, singing. Each act carries its own edge-tts voice."""
    return _j(await _call("GET", "/api/acts"))


@mcp.tool()
async def figg_perform(talent: str, topic: str, mesh_id: str,
                       act: str = "", pet_name: str = "your pet",
                       voice: str = "ryan") -> str:
    """Write, voice and render a performance for a mesh. `talent` is
    comedy|dance|singing, `act` is an id from figg_acts(). ~45s, $0.
    Returns the video URL and the lines it performed."""
    return _j(await _call("POST", "/api/videos",
                          {"talent": talent, "topic": topic, "mesh_id": mesh_id,
                           "act": act, "pet_name": pet_name, "voice": voice,
                           "owner": os.environ.get("FIGG_OWNER", "")}))


@mcp.tool()
async def figg_credits(owner: str = "") -> str:
    """Today's free allowance: sculpts and videos remaining."""
    return _j(await _call("GET", f"/api/credits?owner={owner}"))


async def main() -> None:
    if os.environ.get("MCP_HTTP"):
        print(f"fogg MCP (streamable http) on http://127.0.0.1:{PORT}/mcp", file=sys.stderr)
        await mcp.run_streamable_http_async(host="0.0.0.0", port=PORT)
    else:
        await mcp.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
