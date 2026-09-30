# MCP — the whole library for ChatGPT & friends

> The MCP server exposes the **entire product library** as 15 tools: pets
> (accounts/login/me), meshes (status, measure, print export), the shop
> (products, concepts, Prodigi quote/SKU check), the stage (acts, perform),
> styles and credits. Any MCP client can drive it.

## Endpoints

| Where | URL | Notes |
|---|---|---|
| **Public** | `https://mcp.oddhobb.com/mcp?token=<BRIDGE_TOKEN>` | via the tunnel + bridge; NS must be active |
| Alias while NS pending | `https://pog.pet/mcp?token=<BRIDGE_TOKEN>` | same path, works today |
| Local dev | `http://127.0.0.1:8799/mcp` | server binds **127.0.0.1 only** |

The token is `BRIDGE_TOKEN` — the value in `figgsite/.token` (the same single
secret the site already uses; `API_TOKEN` never leaves the bridge).

## Security model (do not weaken)

- `backend/mcp_server.py` binds **127.0.0.1** — its tools call the API *with
  the service token*, so it must never be internet-reachable directly.
- The bridge owns `/mcp`: **token gate first** (query `?token=` or
  `Authorization: Bearer`), then a streaming proxy (SSE lines and the
  `mcp-session-id` header pass both ways). Verified: **401 without token,
  200 + `text/event-stream` with.**

> **Raw-client note:** Cloudflare 403s script agents like `Python-urllib` on
> POST — set a normal `User-Agent` in any hand-rolled client. Real MCP clients
> (ChatGPT, Claude, Cursor) are unaffected.

## Connect it

**Any remote-MCP client (ChatGPT connectors, Claude, Cursor…):** paste the
public URL *including* the token. That's the whole handshake — no OAuth needed
for the query-token form.

Claude Code:

```bash
claude mcp add --transport http oddhobb "https://pog.pet/mcp?token=<BRIDGE_TOKEN>"
```

Claude Desktop (`claude_desktop_config.json`) / other clients that want JSON:

```json
{ "mcpServers": { "oddhobb": { "url": "https://pog.pet/mcp?token=<BRIDGE_TOKEN>" } } }
```

(Once oddhobb.com's NS is active, swap `pog.pet` → `mcp.oddhobb.com`.)

## The tools

`figg_me` · `figg_create_account` · `figg_login` · `figg_styles` ·
`figg_install_style` · `figg_mesh_status` · `figg_measure` ·
`figg_print_export` · `figg_products` · `figg_concepts` · `figg_quote` ·
`figg_check_sku` · `figg_acts` · `figg_perform` · `figg_credits`

Reachable = every category the rail exposes (Board games, Gifts, Cards are
product filters, not separate backends — see `docs/navigation.md`).
