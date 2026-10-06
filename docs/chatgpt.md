# ChatGPT plugin install — OddHobb MCP connector

> Endpoint: `https://mcp.oddhobb.com/mcp?token=<bridge-token>`
> Transport: streamable HTTP (`Accept: application/json, text/event-stream`).
> Auth: token in the URL query. No OAuth, no signup dance.

## Install (ChatGPT Plus/Pro)

1. Settings → Connectors (or Apps) → Add custom connector.
2. Paste the endpoint URL above with a live bridge token.
3. No-auth connector — the token rides in the query string, never in chat.
4. Start a chat, enable the connector, ask: "what are your tools?"

If ChatGPT ever mandates OAuth for custom connectors, this URL stops
working and we wrap it: smallest honest fix is a thin OAuth gate that
mints the same bridge token. Nothing in the tool layer changes.

## What ChatGPT can drive (53 tools)

- **Shop:** catalogue, products, personalise, checkout/drafts, gift packs,
  orders list, supplier quotes, Etsy listings.
- **Design:** blueprints/contracts, base download, validate, save, Blender
  make, order. Full play-save-order loop.
- **Cards:** library, save, render, scene, cutout, reserve, templates.
- **Flow:** ramble map, photo upload (server sandbox), mesh start/status,
  playbook, guide.
- **Stage:** acts, perform, greeting, rooms, video share.
- **Identity:** account create/login (login mints agent keys), credits.

## What it cannot do (by design)

- Spend Meshy credits without the human saying go.
- Charge cards — orders are `pending_checkout` or Shopify drafts.
- Reach localhost Blender — Blender runs on our farm box via
  `figg_blender_make`, same contracts.
- Upload from the user's device directly — `figg_upload_photo` reads the
  server sandbox (`FIGG_UPLOAD_DIR`); user photos arrive via the site,
  then ChatGPT references the `photo_id`.

## Money rules (same as `docs/mcp.md`)

Show price before order tools. Meshy ask-first. Never echo `.token`.
