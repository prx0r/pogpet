---
name: oddhobb
description: Sell and make personalised pet products on OddHobb via MCP. Use when the buyer wants gifts, cards, jibbits, game pieces, videos, or checkout. Covers the storefront at oddhobb.com, the 55-tool MCP at mcp.oddhobb.com, and Shopify drafts on oddhobb-oufybzg3.myshopify.com.
---

# OddHobb plugin skill — pets become products

Endpoint: `https://mcp.oddhobb.com/mcp?token=<bridge-token>` (streamable
HTTP). Show price before every order tool. Meshy spend ask-first. Orders
never charge — `pending_checkout` or Shopify draft only.

## Buyer journey (follow in order)

1. **Browse.** `figg_catalog` / `figg_product_assets` — 13 live lines with
   GBP prices. Gift derivations come from the shelf, not guessing.
2. **Photo in.** Chat attachment → `figg_upload_chatgpt_file` (ChatGPT
   populates `file` itself) → `photo_id`. No photo: use the demo friend
   Nibble — her mesh `msh_70edae28a4304f4cb7e9` is live for previews.
   Fallback: server sandbox `figg_upload_photo`, or the site upload tab.
3. **Mesh.** `figg_start_mesh(photo_id)` (credits — confirm first), or reuse
   via `figg_mesh_status` / `figg_mesh_manifest`.
4. **Personalise.** `figg_product_personalise` (registry coats/hats/patterns
   only) or `figg_studio_retexture`. Preview inline with
   `figg_preview_image` — never describe a product the buyer can't see.
5. **Pack.** `figg_gift_pack(budget_cents, recipient)` — physical + card +
   free video inside the money. Exact line honoured with cheap addons.
6. **Quote.** `figg_supplier_quote(line)` — makr3d + printie rough costs.
   Estimates; live quotes win.
7. **Checkout.** `figg_checkout` / `figg_fullchain_personalise_order` /
   `figg_design_order` with `fulfil:true` → Shopify draft + `invoice_url`.
   Verify the draft in the Shopify admin (`oddhobb-oufybzg3`), complete or
   delete it there. `figg_studio_orders` lists reservations.

## Designer loop (models play, save, order)

1. `figg_blueprints` — every line's design contract (locked interfaces,
   envelope, material, cost targets). The model designs inside it.
2. `figg_design_base` — master STL (reference lines) or dog GLB (mesh lines).
3. `figg_design_validate` — envelope, material, text zone, farm costs.
4. `figg_design_save` → `design_id` → `figg_design_order`.
5. No local Blender? `figg_blender_make(line, text)` — headless Blender on
   our farm box returns a watertight STL. Local Blender users pair this
   MCP with a BlenderMCP server (see `docs/blender-mcp.md`).

## Cards, videos, viral

- Cards: `figg_card_templates` (paper contracts) → gallery auto-assigns
  from uploads → `figg_card_render` (preview/export/motion) →
  `figg_card_reserve` (export builds first). Tabs stay distinct; video
  add-ons bundle as gift packs, never merged tabs.
- Videos: perform feed only. `figg_video_share` → `?ref=` link; signup
  with the ref installs starter meshes. Prompt + script ride the row.

## Website + Shopify interplay

- The site is the visual half: studio shelf, gift derivations, pack
  builder, share buttons, Nibble demo friend. Same backend, same prices.
- Photos uploaded on oddhobb.com are referenceable by `photo_id` here.
- Orders reserved here appear in the site basket. Drafts complete in
  Shopify admin — invoice links come back in the tool response.

## Hard rules

- Price first, always. Meshy ask-first (prototype 6cr, build 30cr).
- Controlled custom: registry IDs only. No free-form mesh edits.
- Never echo `.token`, bearer URLs, or API keys. Fetch ChatGPT
  `download_url`s server-side; don't log or return them.
