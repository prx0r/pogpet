# Factory MCP — separate server spec

Saved 2026-10-09. Scaffold: `backend/factory_mcp.py` (runs, read tools
live, quote/order stubbed to `needs_input`). Parent docs:
`docs/factory-vision.md`, `docs/factory-developer-product.md`,
`docs/fulfilment-automation.md`.

## Why separate from the OddHobb MCP

Different buyers, different trust. The OddHobb MCP (`backend/mcp_server.py`,
`:8799` full / `:8800` public) sells finished personalised goods to
consumers via agents. The Factory MCP sells *manufacturing capability* to
developers and Blender. Separate process, port, key scope and billable
entity — a developer's runaway script must never be able to touch the
storefront's orders, and a storefront agent must never see factory order
tools. Sharing is data-only: `suppliers.py`, `jlc_materials.json`,
`supplier_catalog.json`, `geometry.py`, `config.jlc_check`.

## Layout

| | OddHobb MCP | Factory MCP |
|---|---|---|
| module | `backend/mcp_server.py` | `backend/factory_mcp.py` (new) |
| name | `oddhobb` | `oddhobb-factory` |
| full tier | `:8799` (bridge token) | `:8803` (`FACTORY_PORT`, keyed) |
| public tier | `:8800` (`PUBLIC_MCP=1`, six tools) | `:8804` (`PUBLIC_MCP=1`, five tools) |
| bridge route | `/mcp` | `/factory/mcp` (to add in bridge) |
| subdomain (later) | mcp.oddhobb.com | factory.oddhobb.com (DNS + ingress) |
| identity | bobdod sells goods | factory agent sells manufacturing |

`:8803` verified free 2026-10-09. Bridge and DNS wiring deliberately not
done yet — other agent mid-edit; the scaffold runs standalone until then.

## Tools

Public (no key — estimate and analyse only, never orderable):

- `factory_tools` — self-describing library (areas + docs).
- `factory_catalog` — JLC materials bible + constraints per process.
- `factory_suppliers` — the 16 lanes (capabilities, order path, price
  grade — never farm names to consumers, full labels to developers).
- `factory_estimate` — material + dims + volume/weight + region → ranked
  feasible lanes with `est_cents` or named gaps (same rules as
  `suppliers.options_for`). Labelled `estimated`: not orderable.
- `factory_analyze` — base64 STL/GLB → dims, volume, manifold verdict +
  `jlc_check` per-process verdicts. Pure local compute, no creds.

Keyed tier (developer key, `X-API-Key` like the storefront):

- `factory_quote` — STUB (`needs_input`): live supplier quote needs JLC
  pricing-API approval. Returns the exact unblock steps, not an error.
- `factory_compare` — STUB: ranks `quoted` offers once quote lands.
- `factory_order_prepare` — STUB: builds a file-hash-pinned order draft.
- `factory_order_confirm` — STUB: disabled until `FACTORY_ENABLE_ORDERS=1`
  AND per-order approval; mirrors the `JLCPCB_ENABLE_ORDERS` pattern.
- `factory_track` — STUB: order/batch status once ordering is live.

Envelope matches the canonical six: `status/summary/artifacts/price/
next_actions`, `needs_input` states instead of errors.

## Auth and money

Developer keys reuse the account-key model (`fagg_`, `X-API-Key`), new
scope `factory`. Spend caps + per-key rate limits before ordering goes
live (designed, not built — same gap as the card MCP). Quotes are free;
orders move money and stay behind prepare→approve→confirm. Every ordered
pair (quoted→landed) feeds the `estimated` cost model — that compounding
data is the product's moat.

## Build phases

1. Scaffold (done): local estimate/analyze/catalog live on `:8803`.
2. Wire: bridge `/factory/mcp` route + `:8804` public tier + tiers health
   line in Flask (ports check extended to 8803/8804).
3. JLC pricing approval → `factory_quote` goes live (TDP + PCB).
4. `factory_order_*` behind approval gate; Sculpteo second lane.
5. `factory.oddhobb.com` + developer beta (estimate+quote, no ordering).

Run: `FACTORY_PORT=8803 MCP_HTTP=1 python3 -m backend.factory_mcp`
(public: `PUBLIC_MCP=1 FACTORY_PORT=8804 …`). stdio without `MCP_HTTP`.
