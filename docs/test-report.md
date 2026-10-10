# Test report — oddhobb

> Run 2026-10-10 11:58 · `scripts/test_site.py` · **80/82 passed** · 0 credits

| # | Result | Test | Detail |
|---|---|---|---|
| 1 | PASS | host oddhobb.com | HTTP 200 |
| 2 | PASS | host www.oddhobb.com | HTTP 200 |
| 3 | PASS | host gifts.oddhobb.com | HTTP 200 |
| 4 | PASS | host boardgames.oddhobb.com | HTTP 200 |
| 5 | PASS | host cards.oddhobb.com | HTTP 200 |
| 6 | PASS | host my.oddhobb.com | HTTP 200 |
| 7 | PASS | page: title branded oddhobb |  |
| 8 | PASS | page: floating account (username+basket) |  |
| 9 | PASS | page: black 3D logo mark |  |
| 10 | PASS | page: username button kept |  |
| 11 | PASS | page: basket button kept |  |
| 12 | PASS | page: prompt-forward hero band |  |
| 13 | PASS | page: my. people grid |  |
| 14 | PASS | page: og meta |  |
| 15 | PASS | page: meta description |  |
| 16 | PASS | page: host->section routing |  |
| 17 | PASS | page: catalog registry fetch |  |
| 18 | PASS | page: tab panels |  |
| 19 | PASS | page: top banner removed |  |
| 20 | PASS | page: text wordmark removed |  |
| 21 | PASS | page: double rail gone |  |
| 22 | PASS | page: no visible pogpet brand |  |
| 23 | PASS | page: my-space copy (star/people) |  |
| 24 | PASS | inline JS syntax (node --check) | clean |
| 25 | PASS | brand_for: oddhobb host |  |
| 26 | FAIL | brand_for: www.ochema.co inherits ochema |  |
| 27 | PASS | brand_for: unknown host falls back, never errors |  |
| 28 | PASS | brand map covers both live domains |  |
| 29 | PASS | GET /api/brand (public, bridge-gated) | oddhobb.com -> oddhobb |
| 30 | PASS | POST /api/session mints anon sig | sig len 32 |
| 31 | PASS | session signs pog_* browser ids | pog_auditx |
| 32 | PASS | session refuses unnamed named-owner claim | HTTP 403 |
| 33 | PASS | non-anon mesh read without sig -> 403 | HTTP 403 |
| 34 | PASS | non-anon rename without sig -> 403 | HTTP 403 |
| 35 | PASS | signed non-anon credits read allowed | HTTP 200 |
| 36 | PASS | login rate limit kicks in (429) | codes=[401, 401, 401, 401, 401, 429] |
| 37 | PASS | security headers on public pages | nosniff/SAMEORIGIN |
| 38 | PASS | greet leads with recipient, not upload | recipient-first positioning |
| 39 | PASS | trademark doc exists |  |
| 40 | PASS | GET /api/seo/products.json (public) | 13 products |
| 41 | PASS | GET /api/seo/faq.json (public) | 422 pairs |
| 42 | PASS | GET /guides/greeting_card (FAQPage schema) | HTTP 200 10792b |
| 43 | PASS | google feed carries AI attributes | HTTP 200 |
| 44 | PASS | shopify feed Q&A in body_html | greeting-card |
| 45 | PASS | GET /api/companygraph (public) | 20 products, 7 caps |
| 46 | PASS | page names bobdod as helper |  |
| 47 | PASS | robots.txt allows AI crawlers | HTTP 200 |
| 48 | PASS | GET /learn/ hub | HTTP 200 |
| 49 | PASS | comparison page + Article JSON-LD | HTTP 200 3105b |
| 50 | PASS | guide has Product + FAQPage JSON-LD | HTTP 200 |
| 51 | PASS | Q&A volume >= 200 pairs (GEO bank) | 422 pairs |
| 52 | PASS | sitemap.xml lists learn + guides | HTTP 200 28 urls |
| 53 | PASS | GET /sections | 5 sections |
| 54 | PASS | GET /catalog | 21 products |
| 55 | PASS | autosort groups (person/photos/r2_key/mesh_id) | 4 groups |
| 56 | PASS | rename round-trip (who's this? -> saved) | Nibble -> NibbleTmp -> Nibble |
| 57 | PASS | GET /flow (sample owner) | stage=ready active=msh_70edae28a4 |
| 58 | PASS | flow hint present | Ready — every product below previews against this  |
| 59 | PASS | sample mesh products (inheritance) | 8 bound |
| 60 | PASS | GET /products (13 previews, cached) | 13 items |
| 61 | PASS | preview image fetchable | HTTP 200 image/png |
| 62 | PASS | GET styles |  |
| 63 | PASS | GET acts |  |
| 64 | PASS | GET credits |  |
| 65 | PASS | GET me |  |
| 66 | PASS | FEED google.xml (public) | HTTP 200, 13 items |
| 67 | PASS | FEED image_link fetchable (no token) | HTTP 200 image/png |
| 68 | PASS | FEED shopify.json (public) | HTTP 200, 13 products |
| 69 | PASS | llms.txt served | HTTP 200 |
| 70 | PASS | shopify-app scaffold | scopes=write_products,read_products,write_product_listings,read_product_listings,write_pub |
| 71 | PASS | sync-catalog.mjs syntax | clean |
| 72 | PASS | API catalog public -> 200 | HTTP 200 |
| 73 | PASS | API bad token -> 401 | HTTP 401 |
| 74 | PASS | POST /premesh (passthrough recipe) | HTTP 200 x-premesh-ok=1 bytes=7643 |
| 75 | PASS | MCP initialize (token) | session fd139cf3 |
| 76 | PASS | MCP tools/list >= 30 | 120 tools |
| 77 | PASS | MCP foundation tools present |  |
| 78 | PASS | MCP tools/call figg_flow | stage=ready mesh=msh_70edae28a4 |
| 79 | FAIL | MCP without token -> public tier | HTTP 502 |
| 80 | PASS | MCP wrong token -> 401 | HTTP 401 |
| 81 | PASS | api.log: no NEW tracebacks during this run | baseline=-1 now=-1 (2 historical = fixed flow bug) |
| 82 | PASS | oddhobb.com final smoke | HTTP 200 |

Re-run: `python3 scripts/test_site.py` (exits non-zero on FAIL).
Covers: 6 hosts + mcp host, page structure & brand, contract APIs, sample-flow, inheritance, preview assets, auth gates, free premesh edge call, public feeds (google.xml, shopify.json, image fetch, llms.txt), shopify-app scaffold + sync syntax, MCP session/tools/call/gate, logs.
