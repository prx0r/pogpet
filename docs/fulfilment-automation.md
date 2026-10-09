# Fulfilment automation — the one-click Blender-to-doorstep path

Saved 2026-10-09. Question: which suppliers let code (not browsers) quote
and order, and what does the Blender plugin look like? Raw docs:
`~/supplier-docs/jlc-api-*.html`, `jlcpcb-mcp-readme.md`, `pcbway-*`,
`wenext-*`, `comparepcb.html`.

## The answer: yes, and half of it already exists

| Supplier | Upload API | Quote API | Order API | Track API | Access |
|---|---|---|---|---|---|
| **JLC (PCB+3DP+parts)** | Gerber zip / STL+STEP | yes | yes (gated) | yes | apply at api.jlcpcb.com, approval on order history |
| Slant 3D | STL | free estimate | yes (charged on process) | webhooks | free dev account, Bearer |
| Shapeways | models/v1 + printability | materials/v1 | orders/v1 | yes | free access |
| Treatstock | upload | price by country | yes | — | key via support |
| Craftcloud/All3DP | model→parse | price compare | cart→order | — | open + MCP via Kiln |
| 3DAPI | SKU flow | yes | Shopify/Etsy/Woo | — | free plan |
| Sculpteo | upload | quote | cart | track | key via partnership |
| Gelato/Mixam/Printify | paper flows | yes | yes | webhooks | keys (none stored) |
| PCBWay (3D/CNC/sheet/mold) | CAD upload, instant quote 80% mats | yes | yes (manual review on top) | dashboard | account; **$25 min order value** + $5–20 startup per material |
| MAKR3D/Printie/Yorkshire/3dfarm | CSV/manual/quote tool | bands/roughs | manual + Shopify/Etsy | — | none needed |
| Xometry | instant quoting engine | yes | yes | — | no open API (partnership/sales) |

MCP today: `Eyalm321/jlcpcb-mcp` (28 tools: LCSC parts search + live
pricing/stock with no creds, official upload/quote/order once approved,
orders default-off). EasyEDA MCP has a quote-only JLC client (ordering
deliberately disabled). Our MCP already drives mesh→personalise→Shopify
draft; JLC order tools slot in behind the same `fulfil:true` pattern with
a spend gate.

## The plugin (design, not built)

Blender side (export operator): select collection → apply scale (mm) →
manifold check → export STL/3MF to temp → call backend with line id +
material + qty. Backend side: `jlc_check()` + supplier `estimate()` →
JLC TDP quote (or farm-lane band) → show landed total → human confirms →
create order → tracking URL back into the line's order row. First version
quotes only (free, no approval needed for LCSC parts data; official quote
needs approved creds). Order placement stays behind an explicit human
gate — same rule as Meshy spend.

Unblock order: apply at api.jlcpcb.com (approval wants order history —
the brick WJP order is the qualifying purchase), then store
`JLC_APP_ID/ACCESS/SECRET` env-only, never in repo.

## New cheap suppliers worth adding

- **PCBWay rapid** (pcbway.com/rapid-prototyping): the only JLC-shaped
  one-stop (PCB + 3D + CNC + sheet + injection + vacuum casting), 200+
  materials, instant quote + DFM, 2-day avg. Caveat: $25 minimum order
  value prices it out of single £3–10 charms — batch lane, not POD lane.
- **WeNext** (wenext.com): instant quote, 30+ plastics / 6 metals,
  ISO-9001 — second quote source for nylon/metal lines.
- **Craftcloud**: no-registration price compare across 150+ shops, MCP
  via Kiln — cheapest-first routing for one-offs.
- **comparepcb.com**: live landed-cost (board + real carrier rates) across
  JLCPCB/PCBWay/NextPCB/Elecrow/Seeed — check here before assuming JLC is
  cheapest to a given country; shipping spreads run 2–3×.
- **PCB bench**: Elecrow (cheap postal shipping), NextPCB (cheap US
  carriers), Seeed Fusion (turnkey assembly, free PCBA shipping),
  ALLPCB — all worth a quote slot for the Glimlings board; OSH Park
  (US-made) and Aisler (EU) for regional overflow.

Registry proposal (not applied — needs owner/other-agent slot): add
`pcbway_rapid` (order api, QUOTE, $25-min flag), `wenext` (order quote,
QUOTE), `comparepcb` (tool, not lane), and a `jlc` entry carrying the
TDP/PCB/Stencil/Parts API paths from `backend/jlc_materials.json`.
