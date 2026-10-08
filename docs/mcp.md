# MCP — agents (ChatGPT / Claude / Muse)

> Public tier (no token): `https://mcp.oddhobb.com/mcp` — exactly six
> intent tools: `oddhobb_people`, `oddhobb_make`, `oddhobb_change`,
> `oddhobb_get`, `oddhobb_add_media`, `oddhobb_buy`. No layout, no fonts,
> no jobs, no providers, no capsules — intent in, finished products out.
> Full tier: same URL `?token=<bridge-token>` or your own API key (all
> machinery + per-customer scoping).
> Local: `MCP_HTTP=1 python3 -m backend.mcp_server` on `:8799` (127.0.0.1);
> public: `PUBLIC_MCP=1 MCP_PORT=8800 MCP_HTTP=1 python3 -m backend.mcp_server`.
> Tools: `pi/.pi/extensions/figgsite.ts` + `backend/mcp_server.py`
> (`PUBLIC_TOOLS` allowlist; tiers pinned by `tests/test_mcp_tiers.py`).
> Rules: `AGENTS.md` · money: `docs/meshy.md` · custom: `docs/studio-custom.md`.

## The canonical six (agent product API)

```
oddhobb_people                           — who can I make things for?
oddhobb_make                             — finished options for person + request
oddhobb_change                           — change this: plain words, new revision
oddhobb_get                              — status + front/inside/back artifacts
oddhobb_add_media                        — add a photo URL to a person
oddhobb_buy                              — checkout URL for the pinned revision
```

Every tool returns `status` (`ready` or `needs_input`), `summary`,
`artifacts`, `price`, and `next_actions`. Auth args are accepted but
optional — connection Bearer wins, then explicit key, then anon.

## What an agent can do (full chain)

```
1. figg_pipeline_status          — health, meshy live/stub, catalogue
2. figg_upload_photo             — customer photo → photo_id
3. figg_start_mesh               — photo_id → mesh job (MESHY — ask user first)
   OR use existing mesh via figg_mesh_status / figg_mesh_manifest
4. figg_mesh_manifest            — machine-readable mesh + allowed props
5. figg_studio_props             — hats, coats, patterns, lines, policy
6. figg_product_assets           — product lines + stills + prices
7. figg_product_personalise      — validate coat/pattern/hat on a line
8. figg_checkout                 — reserve order; fulfil:true → Shopify draft
   OR figg_fullchain_personalise_order  — personalise + order in one call
9. figg_etsy_listing             — Etsy title/tags/sizes for a line

## Design loop (models play, save, order — ChatGPT plugin path)

```
1. figg_blueprints                — every line + design contract (locked,
                                    envelope, material, cost targets)
2. figg_design_base               — download the 3D base (master STL or dog GLB).
                                    ALWAYS start here: the base carries the locked
                                    interfaces already modelled (pin stems, MX sockets,
                                    channels). Adapters win when modelled — e.g. croc_tag
                                    serves its standard pin base even though the line is
                                    face_swap. Free-modelling voids the warranty: v1
                                    designs that skip the base fail validation.
3. figg_design_validate           — check dims/material/text vs the contract
4. figg_design_save               — validated spec stored → design_id
5. figg_blender_make              — Blender on our farm box embosses the text
   onto the line master → watertight STL URL (for agents with no Blender,
   e.g. ChatGPT: same contracts, headless, ~1-2 min)
6. figg_design_order              — reserve/order it; fulfil:true → Shopify draft
   + figg_card_templates          — paper contracts for the 7 card templates
```

Connect ChatGPT (or Claude/Muse) to
`https://mcp.oddhobb.com/mcp?token=<bridge-token>` as an MCP server and the
whole loop is available as tools: pull a contract, fetch the base, design
inside the envelope, validate, save, order. Show price before ordering;
Meshy still ask-first; orders never charge from the API.

ChatGPT + Blender at once: ChatGPT can't reach localhost, so two honest
setups. Either run both our MCP and a BlenderMCP server where the agent
lives (Claude Code/Cursor locally — see `docs/blender-mcp.md`), or let
ChatGPT use Blender through us: `figg_blender_make` runs headless Blender
on our box and hands back the STL. Same contracts either way.

## Money rules for agents

1. **Show the price** before any order/checkout tool.
2. **Never call Meshy** without the human saying go (prototype 6 cr, build 30 cr).
3. **Orders do not charge** — `pending_checkout` or Shopify draft only.
4. **Controlled custom** — pick coat/hat/pattern/line from registries only.
5. Tokens: customer agents use their own session; never echo `.token` to users.

## Example: ChatGPT customise + order

```
User: "Make my dog a chocolate coat with spots on an xmas ornament, £ order"

Agent:
  figg_studio_props()
  figg_fullchain_personalise_order({
    line: "ornament", coat: "chocolate", pattern: "spots",
    hat: "santa", qty: 1, fulfil: true
  })
  → show price £12.99 + order id + Shopify draft (if configured)
```

## Example: gift card

```
figg_checkout({ line: "gift_card", amount_cents: 2500, qty: 1, fulfil: true })
```

## Example: personal Xmas card (after card UI)

```
figg_etsy_listing({ product_id: "xmas_card" })
→ title, tags, sizes A6/5x7/A5, materials, processing days
```

## Auth

| Who | How |
|---|---|
| Site visitor | bridge injects `window.__FIGG_TOKEN` |
| Public MCP | `?token=` = BRIDGE_TOKEN (`.token`) |
| Named owner | `X-API-Key` or owner-sig session |
| Server-side | `API_TOKEN` (never in the browser) |

## Docs

- `docs/studio.md` — studio + products API
- `docs/studio-custom.md` — controlled custom policy
- `docs/shopify-auth.md` — draft order token exchange
- `docs/muse-mcp-design.md` — original Muse journey design
- `HANDOVER.md` — session state
