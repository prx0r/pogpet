# Multi-brand: one codebase, many storefronts

Date: 2026-09-30 · Round 5 · Status: seam live, ochema.co pending NS

## Why

oddhobb.com is live. ochema.co was bought the same day. The question:
rebuild the site per domain, or make the structure transferable? Answer —
**transferable**: same Flask app, same bridge, same MCP, same premesh
pipeline; brands are a config map + per-request Host resolution. Adding a
brand is one dict entry, not a fork.

## The seam (all in-repo, nothing private)

```
backend/config.py
  BRANDS = {
    "oddhobb.com": {"brand": "oddhobb", "tagline": "...",
                    "support": "support@oddhobb.com"},
    "ochema.co":   {"brand": "ochema",  "tagline": "...",
                    "support": "support@ochema.co"},
  }
  DEFAULT_BRAND_HOST = "oddhobb.com"
  def brand_for(host) -> dict      # www. stripped; subdomains inherit
                                   # parent domain; unknown -> default
                                   # (never 404, never leak)

backend/server.py
  GET /api/brand                   # answers per request Host
  premesh.normalize(..., zone=config.brand_for(request.host)["host"])
                                   # staged sources live on the zone that
                                   # actually serves them

site/index.html
  window.__BRAND__ + applyBrand()  # boot fetches /api/brand, repaints
  initBrand() on window load       # title, boot/greeting/topbar marks,
                                   # section labels ("My oddhobbs" ->
                                   # "My ochas" etc.), AI prompt line
                                   # — no hardcoded brand strings left
```

Verified: `brand_for("oddhobb.com")` → oddhobb/support@oddhobb.com;
`brand_for("www.ochema.co")` → ochema/support@ochema.co (subdomain
inherits); unknown host → safe oddhobb fallback. Public tunnel check:
`GET https://oddhobb.com/backend/api/brand` returns the oddhobb record.

## ochema.co — what's done vs what waits on you

| Step | Status |
|---|---|
| Cloudflare zone created (account same as oddhobb) | done — id `1f0d6f8d88dec141c2d25011659e391c` |
| **Nameservers to paste at Namecheap** | `gina.ns.cloudflare.com` / `pete.ns.cloudflare.com` |
| Email routing rule `support@ochema.co` → tradesprior@gmail.com | done (activates with zone) |
| CNAMEs ochema.co + www → tunnel `54295d83-…cfargotunnel.com`, proxied | done |
| Tunnel ingress entries in `~/.cloudflared/figgsite.yml` | done, seamless rollover, pog.pet still 200 |
| BRANDS entry + /api/brand + frontend repaint | done |
| Zone **status** | **pending — waiting on NS at Namecheap** |

After the NS flip: zone goes active → MX/SPF apply → support@ochema.co
forwards → DNS records resolve → `https://ochema.co/` serves the same
storefront branded **ochema**. Zero code change.

To add a third brand later: one entry in `config.BRANDS`, optional
section host mapping if it needs its own rail — everything else follows.

## Storefront / agent surface per brand

- Same sections registry (`GET /api/sections`), same catalog, same MCP
  (gate token per host via the same bridge), same feeds — brand only
  changes painted strings + support address + premesh zone.
- Agents (Muse/ChatGPT) see the same contract on either domain; llms.txt
  is host-agnostic; MCP URL pattern documented there.

## Shopify + 3D previews (researched this round, adopted pattern)

See `shopify-app/ODDHOBB.md` for the full table. Short version:

- **Adopt:** Google `<model-viewer>` + Shopify native product 3D media
  (or `custom.model_3d_url` metafield as fallback) — the exact pattern in
  the cloned public repo `brennan252/Immersive-Product-Display`
  (reference-only clone in `/home/ubuntu/refs/`, not vendored): one Liquid
  snippet, poster slot, free AR (Quick Look + Scene Viewer).
- **Skip:** heavyweight theme engines (WebGI etc.).
- **Our source assets:** Meshy-hung GLB (`data/uploads/chibi-figure-hook.glb`)
  + PNG poster (already mirrored in `data/productimg/` → public `/img/`).
- **Next for a real Shopify store:** `SHOPIFY_STORE` + `SHOPIFY_ADMIN_TOKEN`
  → `npm run sync:catalog` (upsert-by-handle, `--dry-run` first).

## Money rules (unchanged, apply per brand)

Meshy/paid API usage always asks first. Ledger
`data/meshy_credits.jsonl`. Balance 1,056 cr after the dog mesh. Amend /
re-render = Blender only, 0 credits.
