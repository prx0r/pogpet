# SEO implementation status

Playbook: `docs/seo.md` · Updated: 2026-09-30

## Wired (live)

| Item | Where |
|------|--------|
| SEO pack (8 AI attributes + Q&A + docs) for 15 products | `backend/config.py` `SEO` |
| Feed items carry highlights, details, variants, item group, related, Q&A, doc links | `_feed_items` in `backend/server.py` |
| Google Merchant RSS + custom labels + item_group_id + product_type | `GET /backend/api/feeds/google.xml` |
| Shopify-shaped feed with Q&A in `body_html` + SEO block | `GET /backend/api/feeds/shopify.json` |
| Full AI pack JSON (public) | `GET /api/seo/products.json` |
| Flat Q&A pairs (public) | `GET /api/seo/faq.json` |
| Crawlable buyer guides + FAQPage JSON-LD | `GET /guides/<product_id>` |
| Organization JSON-LD + products.json alternate link | `site/index.html` |
| Agent pointers | `site/llms.txt` |
| Bridge: `/api/seo/*` and `/guides/*` ungated | `bridge/llm_bridge.py` |

## Still to do (owner actions + build)

1. **Google Merchant Center account** — verify oddhobb.com, submit
   `https://oddhobb.com/backend/api/feeds/google.xml`, enable AI insights.
2. **Pin designs** — 5 vertical 2:3 pins per product (design work, not code).
3. **PDF companion guides** — HTML guides are live at `/guides/<id>`; export
   PDFs later if Google prefers them (HTML+FAQPage schema is crawlable now).
4. **Popularity rank** — needs real sales data (blocked on checkout).
5. **Pin daily** — ops, not code. Calendar in `docs/seo.md`.
6. **Pinterest catalog** — after Merchant Center; reuse the same feed attributes.

## Research notes (not wired)

- **CompanyGraph** (`prx0r/agentcom` `companygraph/`): FACTS / RESOURCES /
  CAPABILITIES model — products, policies, Shopify as a resource, MCP
  capabilities with authorization. Pattern to expose OddHobb to agents
  without a custom dashboard. Reference: `/home/ubuntu/refs/agentcom/companygraph/`.
- **XMRBot 0.4 private procurement** (`prx0r/agentcomfinal`
  `packages/xmrbot-private-procurement-v0.4/`): Monero provider fabric with
  grant→gate→execute model, non-custodial (no seed export), proposal-first
  MCP. Could inform a future "private checkout" experiment. **Not wired** —
  legal/compliance review required before any Tor/XMR payment path touches
  this storefront. OddHobb sells legal personalised goods via normal
  checkout; XMR/Tor remains a research thread only.

## Discovery stack (2026-09-30, second pass)

| Item | Status |
|------|--------|
| robots.txt allowing GPTBot, ClaudeBot, PerplexityBot, Google-Extended, Bingbot, etc. | live `site/robots.txt` |
| Product JSON-LD + FAQPage on `/guides/<id>` | live (price GBP, brand OddHobb) |
| GEO knowledge pages `/learn/*` (definitions + comparison tables) | live — 4 pages + hub |
| Article JSON-LD on learn pages | live |
| sitemap.xml (shop, learn, guides, feeds, SEO JSON) | live |
| Q&A volume | **422 pairs** public via `/api/seo/faq.json` (GEO bank + product-specific; target ~30/product met) |
| Company graph + bobdod | live `GET /api/companygraph`, MCP `figg_companygraph` |

### GEO pages

- `/learn/` — hub
- `/learn/what-is-a-pet-figurine` — definition
- `/learn/oddhobb-vs-pet-portraits` — comparison table (OddHobb vs traditional)
- `/learn/how-personalised-pet-products-work` — how-to
- `/learn/best-gifts-for-pet-owners` — gift comparison table

### Still owner ops (not code)

Etsy shop · Pinterest Business + pin designs · Merchant Center submit ·
pin daily · sales data for popularity rank.
