# Studio + Products — modular character select & storefront

> Status: LIVE (2026-10-02). Two tabs, one mesh, modular props.
> **Studio** = white character-select + loadout config (**no prices**).
> **Products** = storefront (prices, one-click order, MCP personalise).

## Studio (config page)

- White stage (`panel.white`)
- **Character strip + ← → arrows** — reuse the dog GLB now; more meshes later
- **Calling card** under the stage (exact product portrait + mesh id)
- Loadout chips: line · coat · hat (restricted per line assets)
- Agent box freeform → loadout
- Save loadout → localStorage for Products
- Later: wink / signature move / intro tune on this stage (freaktown vision)

## Products (storefront)

- Cards per `STUDIO_LINES` with relevant assets:
  - **Xmas ornament** → santa hat + all coats
  - **Keychain** → coats only
  - **Brick** → soon
- Configure coat/hat → stills refresh
- **One-click order** → `orders` table, `pending_checkout` (no charge)
- MCP panel on the detail card

## Contract

| Method | Path | Does |
|---|---|---|
| GET | `/api/studio` | character select + loadout registry + calling_card |
| GET | `/api/studio/stills` | stills for line/coat/hat |
| POST | `/api/studio/customise` | apply loadout |
| GET | `/api/products/studio` | storefront lines + assets + prices + stills |
| POST | `/api/products/personalise` | MCP/agent personalise |
| POST | `/api/products/order` | one-click order → pending_checkout |
| POST | `/api/studio/order` | same store (legacy path) |

MCP: `figg_studio_state` · `figg_studio_customise` · `figg_product_assets` ·
`figg_product_personalise` · `figg_checkout` · `figg_studio_order`.

## Registry

- `config.STUDIO_LINES` — per-line `assets.hats` / `assets.coats` / theme
- `config.STUDIO_COATS`, `config.STUDIO_HATS`
- Stills: `data/productimg/prod/` → `/img/prod/` (exact + coats + santa)

## Rules

1. Studio has **no pricing** — that is Products.
2. No metal hardware — loop is in the GLB.
3. Coat = preview grade; production multi-colour is a live quote.
4. Order does not charge — Stripe/Shopify next.
5. 0 Meshy credits for previews.

## Next

- [ ] Brick mesh → enable brick line
- [ ] Animation layer on Studio stage (wink / move / intro tune)
- [ ] Stripe / Shopify checkout on `pending_checkout`
- [ ] Texture/decal personalisation beyond coat+hat
- [ ] MCP journey rows in `docs/muse-mcp-design.md`
