# MCP — agents (ChatGPT / Claude / Muse)

> Public endpoint: `https://mcp.oddhobb.com/mcp?token=$(cat .token)`
> Local: `MCP_HTTP=1 python3 -m backend.mcp_server` on `:8799` (127.0.0.1).
> Tools: `pi/.pi/extensions/figgsite.ts` + `backend/mcp_server.py`.
> Rules: `AGENTS.md` · money: `docs/meshy.md` · custom: `docs/studio-custom.md`.

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
```

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
