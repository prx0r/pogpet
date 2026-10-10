# Test report — oddhobb

> Run 2026-10-10 04:56 · `scripts/test_site.py` · **77/79 passed** · 0 credits

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
| 23 | FAIL | brand_for: www.ochema.co inherits ochema |  |
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
| 35 | PASS | greet leads with recipient, not upload | recipient-first positioning |
| 36 | PASS | trademark doc exists |  |
| 37 | PASS | GET /api/seo/products.json (public) | 13 products |
| 38 | PASS | GET /api/seo/faq.json (public) | 422 pairs |
| 39 | PASS | GET /guides/greeting_card (FAQPage schema) | HTTP 200 10792b |
| 40 | PASS | google feed carries AI attributes | HTTP 200 |
| 41 | PASS | shopify feed Q&A in body_html | greeting-card |
| 42 | PASS | GET /api/companygraph (public) | 20 products, 7 caps |
| 43 | PASS | page names bobdod as helper |  |
| 44 | PASS | robots.txt allows AI crawlers | HTTP 200 |
| 45 | PASS | GET /learn/ hub | HTTP 200 |
| 46 | PASS | comparison page + Article JSON-LD | HTTP 200 3105b |
| 47 | PASS | guide has Product + FAQPage JSON-LD | HTTP 200 |
| 48 | PASS | Q&A volume >= 200 pairs (GEO bank) | 422 pairs |
| 49 | PASS | sitemap.xml lists learn + guides | HTTP 200 28 urls |
| 50 | PASS | GET /sections | 5 sections |
| 51 | PASS | GET /catalog | 21 products |
| 52 | PASS | autosort groups (person/photos/r2_key/mesh_id) | 4 groups |
| 53 | PASS | rename round-trip (who's this? -> saved) | Nibble -> NibbleTmp -> Nibble |
| 54 | PASS | GET /flow (sample owner) | stage=ready active=msh_70edae28a4 |
| 55 | PASS | flow hint present | Ready — every product below previews against this  |
| 56 | PASS | sample mesh products (inheritance) | 8 bound |
| 57 | PASS | GET /products (13 previews, cached) | 13 items |
| 58 | PASS | preview image fetchable | HTTP 200 image/png |
| 59 | PASS | GET styles |  |
| 60 | PASS | GET acts |  |
| 61 | PASS | GET credits |  |
| 62 | PASS | GET me |  |
| 63 | PASS | FEED google.xml (public) | HTTP 200, 13 items |
| 64 | PASS | FEED image_link fetchable (no token) | HTTP 200 image/png |
| 65 | PASS | FEED shopify.json (public) | HTTP 200, 13 products |
| 66 | PASS | llms.txt served | HTTP 200 |
| 67 | PASS | shopify-app scaffold | scopes=write_products,read_products,write_product_listings,read_product_listings,write_pub |
| 68 | PASS | sync-catalog.mjs syntax | clean |
| 69 | PASS | API catalog public -> 200 | HTTP 200 |
| 70 | PASS | API bad token -> 401 | HTTP 401 |
| 71 | PASS | POST /premesh (passthrough recipe) | HTTP 200 x-premesh-ok=1 bytes=7643 |
| 72 | PASS | MCP initialize (token) | session 9eb1d10a |
| 73 | PASS | MCP tools/list >= 30 | 109 tools |
| 74 | PASS | MCP foundation tools present |  |
| 75 | PASS | MCP tools/call figg_flow | stage=ready mesh=msh_70edae28a4 |
| 76 | FAIL | MCP without token -> public tier | HTTP 502 |
| 77 | PASS | MCP wrong token -> 401 | HTTP 401 |
| 78 | PASS | api.log: no NEW tracebacks during this run | baseline=-1 now=-1 (2 historical = fixed flow bug) |
| 79 | PASS | oddhobb.com final smoke | HTTP 200 |

Re-run: `python3 scripts/test_site.py` (exits non-zero on FAIL).
Covers: 6 hosts + mcp host, page structure & brand, contract APIs, sample-flow, inheritance, preview assets, auth gates, free premesh edge call, public feeds (google.xml, shopify.json, image fetch, llms.txt), shopify-app scaffold + sync syntax, MCP session/tools/call/gate, logs.
