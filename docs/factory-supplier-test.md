# Factory supplier test — Blender → STL → verdicts → lanes (2026-10-09)

Test part: parametric golf marker ("BUSTER", 24mm) designed headless in
Blender 5.0.1 via `scripts/parametric_marker.py` → `/tmp/factory_test_marker.stl`
(manifold-clean, 4348 tris). Run through `backend/factory_mcp.py` live.

## Factory verdicts on the part

- `factory_analyze` (FDM/SLA/SLS_MJF/WJP_TOUGH): **PASS** — 24.0×23.6×2.8mm,
  0.98cm³, ~1.22g PLA, manifold 0. (BJ: laser-note only, correct.)
- `factory_estimate` (PLA, UK): Printie **£0.14** · MAKR3D **£1.29** (band) ·
  3dfarm **£3.14** — live evidence its coded rate runs ~22× the farm lane
  (SUSPECT flag confirmed, not just suspected). 8 more lanes feasible but
  QUOTE-grade; 3 paper lanes correctly infeasible.

## LIVE API quotes (actually called, 2026-10-09)

- **Slant 3D (US lane) via public MCP** (`slant3d.com/mcp`, no key): marker
  quoted **$1.21 print / $2.44 unit @1, $1.33 @100, $1.09 @1000**, PLA black,
  lead 3–5 business days, quote_id `mcp-34e8f0b1…`. Plus real DFM: thin wall
  0.44mm flagged problem (our relief text — `jlc_check` passed it, the live
  slicer didn't; proxy < slicer, noted). First attempt failed instructively:
  meter-unit STL read as 0.024mm ("out of bounds") — the plugin must export
  mm; rescale → accept.
- **Mixam (paper, keyless public API)**: 25 greeting cards **£43.50 best**
  (4-day, UK, delivery Oct 15) with express ladder to £53.50 next-day.
  Full 76-product catalogue + metadata + offers all open, no account.
- **Gelato**: owner key stored env-only 2026-10-09, authenticated (200 on
  `/v4/orders`, account empty). No public catalog endpoint — productUid must
  come from the dashboard Product Catalog; then free auto-cancelled test
  orders via the API Portal before any live card shootout.
- **Prodigi (paper)**: canvas 10×10 GB **£28.62** landed (item £16 + Evri
  £7.85 + tax £4.77). Owner key stored env-only 2026-10-09, verified live.
  Card SKU resolves via check_sku; its quote hits an attribute error in our
  wrapper (`wrap: White` rejected — one-line tracked-file fix, held while
  the tree is busy; canvas unaffected). API docs imported
  (`prodigi-api-docs/reference/print-api` snapshots); sandbox
  (api.sandbox.prodigi.com) available for free order-flow testing. Card SKU hits an attribute error in our wrapper
  (`wrap: White` rejected — tracked `prodigi.py` issue, canvas unaffected).
- **MAKR3D API**: live at `makr3d.app/api/v1` (OpenAPI 3.1, Bearer
  `m3d_live_`, scoped keys) — needs owner-created key from dashboard
  Settings → API keys before first live call.
- `factory_quote` now fans out live: kind=3d → Slant; kind=card → Mixam +
  Prodigi attempt, ranked cheapest-first with delivery dates. Verified
  running 2026-10-09 (fresh quote_ids per call).

## Decision rule (one winner, capability gates price)

`factory_quote` returns ONE decision: mono marker → Slant $2.44 ("cheapest
landed meeting all requirements"); same file with `full_color=True` →
REFUSED with the JLC path (three Slant offers rejected as monochrome,
nothing mis-routed); 25 cards with 2-day deadline → Mixam £46.50 express
wins over the £43.50 standard. Full-colour-capable lanes today: JLC WJP
only (verified sources); farm "multicolour" is ≤4 filaments, not
photographic colour. Quality bar cited on every full-colour verdict: matte,
no metallic, sun-fade, walls ≥1.0mm (Tough 0.8), emboss ≥0.8mm.

## Own-JLC pricing (no approval needed to price)

`_jlc_rough` in the factory prices JLC from published floors + $/g, graded
ROUGH, ex-tax/shipping — verified live: full-colour → $5 WJP floor; PA12
10cm³ → $2.78 at the published $0.275/g (farm lane correctly infeasible —
no nylon); 50g steel → $10.50 at $0.21/g. ROUGH never outranks LIVE and
never orders; ordering still needs the TDP approval. Data lives in
`jlc_materials.json rough_pricing` with standard densities marked as such.
- Everything else: local math (bands/roughs) or `needs_input` stubs. Only
  Slant/Mixam/Prodigi have been called live — Slant's keyless MCP and
  Mixam's keyless API are the only quotable endpoints available with zero
  signup, which is why US-first starts at Slant.

## Per-supplier live availability (tested today, no creds stored)

| Supplier | Reachable | Callable without approval/key | Verdict |
|---|---|---|---|
| JLC API platform | 200 | quote/order need approved creds | stub stands; brick order = approval history, then apply |
| JLC web quote | 200 | browser upload only | manual path open |
| MAKR3D / Printie | local math | yes — bands/roughs live in estimator | ordering = Shopify/draft + manual |
| Prodigi | **LIVE quote £28.62** (canvas 10×10, GB, Evri, incl tax) | yes — key in `.env` | only order-capable lane today; quote free, orders never placed by agents |
| Slant3D / Shapeways / Treatstock | 200/403/200 | need Bearer/API key (none stored) | blocked on keys, all free to obtain |
| Sculpteo | 403 (bot-wall scripts; browser fine) | key via partnership | blocked on partnership |
| Craftcloud | 200 | web quotes no-reg; API via Kiln MCP (not installed) | install Kiln MCP for machine path |
| PCBWay | 200 | web instant quote (account); partner API is PCB-only | $25-min rule noted; 3D/CNC = web path |
| WeNext | 200 | web instant quote | second-quote source, no API found |
| Xometry | 429 (rate-limited, backed off) | engine only, no open API | partnership/sales path |
| comparepcb | 200 | free landed-cost compare, no account | use before every PCB order |

No paid orders placed or placeable: JLC needs approval, Slant/Shapeways/
Treatstock need keys, factory order tools are default-off stubs.

## Bugs found by live testing (filed, not fixed — tracked files)

1. `backend/geometry.py mesh_report(units='m')`: scales data to mm then
   multiplies volume by 1e6 again (marker read 980000cm³). Compensated
   inside `factory_analyze`; upstream fix is one line when tree is quiet.
   Lesson for the Blender plugin: export mm or pass `units='m'`.
2. `backend/config.py jlc_check('CNC')`: `KeyError 'min_wall_mm'` — CNC
   row has detail/UV/laser but no wall rule, and the checker assumes it.
   `factory_analyze` catches it into a labelled gap verdict.

## What "fulfilled" means per lane today

Paper/merch: Prodigi live (quote→draft→order path exists, human-gated).
Farm lane: estimate→manual order. JLC/Slant/network lanes: estimate→apply
for creds→quote→order. The Blender plugin's Phase 1 (quote router) is
proven working; Phase 2 waits on one approval (JLC) and three free keys.

## MCP wire test (2026-10-09, `:8803`)

Server up (`MCP_HTTP=1 FACTORY_PORT=8803 python3 -m backend.factory_mcp`).
Over-the-wire handshake + `tools/list` (11 tools) + `tools/call`
`factory_estimate` (11 feasible incl. JLC ROUGH) + `tools/call`
`factory_quote` card/25/2-day (decided Mixam £46.50 express) — all green.
Public tier (`:8804`) reserved, not started. Connect any MCP client at
`http://127.0.0.1:8803/mcp` (local; bridge route + subdomain are Phase 2).
