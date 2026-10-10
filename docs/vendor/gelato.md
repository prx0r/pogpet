# Gelato API — imported 2026-10-10

Key: `GELATO_API_KEY` in `.env` (verified live: bad ids return 404
NOT_FOUND, not 401). Client: `backend/gelato.py` (staged until
`GELATO_STORE_ID` + a dashboard templateId exist).
Base: `https://ecommerce.gelatoapis.com/v1`, auth `X-API-KEY`.
Sources: dashboard.gelato.com/docs/ecommerce, support.gelato.com
(Create Product API, Personalization Studio, design templates).

## What exists (native template fill)

1. Build a product template in the dashboard (variants, mockups, prices).
2. Editor → add image layer, unique layer name (e.g. `HeroFace`).
   `GET /v1/templates/{{templateId}}` returns variants + imagePlaceholders
   (name, printArea, mm). Text layers can be personalisable (mandatory,
   char limits, conditional reflow) via Personalization Studio.
3. `POST /v1/stores/{{storeId}}/products:create-from-template` with
   `{templateId, title, description, tags, variants: [{templateVariantId,
   imagePlaceholders: [{name, fileUrl, fitMethod?: slice|meet}]}]}`.
   Products + mockups render in the background. Tags ≤13 (Etsy ≤20 chars).

## Range notes (2026-10)

Paper/stationery (cards, postcards, notepads, notebooks, calendars),
wall art, mugs, apparel. **No wrapping paper found in range** — Gelato
enters our stack on cards/stationery, not wrap. Paper lanes in
supplier_catalog.json stay QUOTE/unwired until a template exists.
