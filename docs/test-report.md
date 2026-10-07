# Test report — oddhobb

> Run 2026-10-07 09:44 · `scripts/test_site.py` · **78/78 passed** · 0 credits

| # | Result | Test | Detail |
|---|---|---|---|
| 1 | PASS | host oddhobb.com | HTTP 200 |
| 2 | PASS | host www.oddhobb.com | HTTP 200 |
| 3 | PASS | host gifts.oddhobb.com | HTTP 200 |
| 4 | PASS | host boardgames.oddhobb.com | HTTP 200 |
| 5 | PASS | host cards.oddhobb.com | HTTP 200 |
| 6 | PASS | host my.oddhobb.com | HTTP 200 |
| 7 | PASS | page: title branded oddhobb |  |
| 8 | PASS | page: Amazon topbar (search+account) |  |
| 9 | PASS | page: persistent category strip |  |
| 10 | PASS | page: storefront search box |  |
| 11 | PASS | page: prompt-forward hero band |  |
| 12 | PASS | page: my. people grid |  |
| 13 | PASS | page: og meta |  |
| 14 | PASS | page: meta description |  |
| 15 | PASS | page: host->section routing |  |
| 16 | PASS | page: catalog registry fetch |  |
| 17 | PASS | page: tab panels |  |
| 18 | PASS | page: double rail gone |  |
| 19 | PASS | page: no visible pogpet brand |  |
| 20 | PASS | page: my-space copy (star/people) |  |
| 21 | PASS | inline JS syntax (node --check) | clean |
| 22 | PASS | brand_for: oddhobb host |  |
| 23 | PASS | brand_for: www.ochema.co inherits ochema |  |
| 24 | PASS | brand_for: unknown host falls back, never errors |  |
| 25 | PASS | brand map covers both live domains |  |
| 26 | PASS | GET /api/brand (public, bridge-gated) | oddhobb.com -> oddhobb |
| 27 | PASS | POST /api/session mints anon sig | sig len 32 |
| 28 | PASS | session signs pog_* browser ids | pog_auditx |
| 29 | PASS | session refuses unnamed named-owner claim | HTTP 403 |
| 30 | PASS | non-anon mesh read without sig -> 403 | HTTP 403 |
| 31 | PASS | non-anon rename without sig -> 403 | HTTP 403 |
| 32 | PASS | signed non-anon credits read allowed | HTTP 200 |
| 33 | PASS | login rate limit kicks in (429) | codes=[401, 401, 401, 401, 401, 429] |
| 34 | PASS | security headers on public pages | nosniff/SAMEORIGIN |
| 35 | PASS | trademark doc exists |  |
| 36 | PASS | GET /api/seo/products.json (public) | 13 products |
| 37 | PASS | GET /api/seo/faq.json (public) | 422 pairs |
| 38 | PASS | GET /guides/greeting_card (FAQPage schema) | HTTP 200 10792b |
| 39 | PASS | google feed carries AI attributes | HTTP 200 |
| 40 | PASS | shopify feed Q&A in body_html | greeting-card |
| 41 | PASS | GET /api/companygraph (public) | 20 products, 7 caps |
| 42 | PASS | page names bobdod as helper |  |
| 43 | PASS | robots.txt allows AI crawlers | HTTP 200 |
| 44 | PASS | GET /learn/ hub | HTTP 200 |
| 45 | PASS | comparison page + Article JSON-LD | HTTP 200 3105b |
| 46 | PASS | guide has Product + FAQPage JSON-LD | HTTP 200 |
| 47 | PASS | Q&A volume >= 200 pairs (GEO bank) | 422 pairs |
| 48 | PASS | sitemap.xml lists learn + guides | HTTP 200 28 urls |
| 49 | PASS | GET /sections | 5 sections |
| 50 | PASS | GET /catalog | 21 products |
| 51 | PASS | autosort groups (person/photos/r2_key/mesh_id) | 1 groups |
| 52 | PASS | rename round-trip (who's this? -> saved) | Nibble -> NibbleTmp -> Nibble |
| 53 | PASS | GET /flow (sample owner) | stage=ready active=msh_70edae28a4 |
| 54 | PASS | flow hint present | Ready — every product below previews against this  |
| 55 | PASS | sample mesh products (inheritance) | 8 bound |
| 56 | PASS | GET /products (13 previews, cached) | 13 items |
| 57 | PASS | preview image fetchable | HTTP 200 image/png |
| 58 | PASS | GET styles |  |
| 59 | PASS | GET acts |  |
| 60 | PASS | GET credits |  |
| 61 | PASS | GET me |  |
| 62 | PASS | FEED google.xml (public) | HTTP 200, 13 items |
| 63 | PASS | FEED image_link fetchable (no token) | HTTP 200 image/png |
| 64 | PASS | FEED shopify.json (public) | HTTP 200, 13 products |
| 65 | PASS | llms.txt served | HTTP 200 |
| 66 | PASS | shopify-app scaffold | scopes=write_products,read_products,write_product_listings,read_product_listings,write_pub |
| 67 | PASS | sync-catalog.mjs syntax | clean |
| 68 | PASS | API catalog public -> 200 | HTTP 200 |
| 69 | PASS | API bad token -> 401 | HTTP 401 |
| 70 | PASS | POST /premesh (passthrough recipe) | HTTP 200 x-premesh-ok=1 bytes=7643 |
| 71 | PASS | MCP initialize (token) | session 7a0498bb |
| 72 | PASS | MCP tools/list >= 30 | 75 tools |
| 73 | PASS | MCP foundation tools present |  |
| 74 | PASS | MCP tools/call figg_flow | stage=ready mesh=msh_70edae28a4 |
| 75 | PASS | MCP without token -> public tier | HTTP 200 |
| 76 | PASS | MCP wrong token -> 401 | HTTP 401 |
| 77 | PASS | api.log: no NEW tracebacks during this run | baseline=0 now=0 (2 historical = fixed flow bug) |
| 78 | PASS | oddhobb.com final smoke | HTTP 200 |

Re-run: `python3 scripts/test_site.py` (exits non-zero on FAIL).
Covers: 6 hosts + mcp host, page structure & brand, contract APIs, sample-flow, inheritance, preview assets, auth gates, free premesh edge call, public feeds (google.xml, shopify.json, image fetch, llms.txt), shopify-app scaffold + sync syntax, MCP session/tools/call/gate, logs.
