# Navigation architecture — sections, subdomains, topbar

> Built 2026-09-30 (the10 in `docs/todo.md`). The vision behind it:
> `docs/oddhobb-vision.md`.

## One source of truth

`backend/config.py`:

- **`SECTIONS`** — ordered list: `{id, label, icon, panel, host}`.
  `panel` = which tab the section opens (`shop` for catalog filters, `upload`
  for the roster), `host` = the subdomain that deep-links into it ("" = none).
- **`SECTION_OF`** — product id → section id. Products absent from the map live
  in **All** only (deliberate: the digital experiences — video/comedy/AR —
  have no section until we invent one).

Served at **`GET /api/sections`** → `{sections, section_of, host_section}`.
Changing a section is a config edit; nothing else needs touching.

```
all          → shop (no filter)
board-games  → shop, section=board-games   ← boardgames.oddhobb.com
gifts        → shop, section=gifts         ← gifts.oddhobb.com
cards        → shop, section=cards         ← cards.oddhobb.com
my           → upload panel (roster)       ← my.oddhobb.com
```

## Topbar + category strip (one nav layer, Amazon bones)

The double rail (tabrail + seclrail) is gone — one layer only:

- **`.topbar`** (fixed, `left:72px`, above the tabrail at z70): brand mark,
  `#qsearch` store-wide search, account + cart buttons. Content offset lives
  in `.app` (`padding-left:72px; padding-top:102px`).
- **`.catstrip`** (inside the topbar, horizontal scroll row): the category
  pills, rendered from the fetched registry (`initSections()`), with the same
  inline fallback list so it paints before the fetch lands. Clicking a catalog
  section opens the shop tab filtered; `my` opens the people panel.
- **Search**: `#qsearch` `input` event sets `state.q`; typing with the shop
  closed jumps to it. `applySection()` matches
  `section AND (label contains q)` — cards carry `data-label` at render time.
  Clearing the box restores section-only filtering.
- **Ledes follow the section**: `setSection()` rewrites `#shop-lede` from the
  registry `blurb` (`#/s/cards` literally pitches the card line while you shop
  it) — this is what makes `cards.oddhobb.com` feel like its own shelf.
- **Prompt-forward hero**: `#shop-hero` headline + `#hero-q`/`#hero-go` drops
  the visitor's words straight into the docked chat input (`#ti`). Higgsfield
  skin on the catalog bones: `.card:hover` lift + violet glow, dark cinematic
  surfaces throughout.

### Filtering

Both card sources carry `data-sec`:

- Prodigi mockups: `item.section` straight from `/api/products`
- mesh products: `p.section` from `/api/meshes/<id>/products`

`applySection()` hides non-matching cards and appends `.secempty` when a
section has no stock (Board games gets its own "jigsaw lands here first"
copy). The shop status line prefixes the active section.

## Host → section routing

`initSections()` runs on load: hash (`#/s/gifts`) wins, else
`host_section[location.hostname]` — so `cards.oddhobb.com` boots straight into
Cards. State is reflected back to `#/s/<id>` so URLs stay shareable.

## Subdomains

| Host | Section | Edge status |
|---|---|---|
| `oddhobb.com`, `www` | all | CNAME + ingress live (NS pending 2026-09-30) |
| `gifts.oddhobb.com` | gifts | CNAME + ingress live |
| `boardgames.oddhobb.com` | board-games | CNAME + ingress live |
| `cards.oddhobb.com` | cards | CNAME + ingress live |
| `my.oddhobb.com` | my (roster) | CNAME + ingress live |
| `mcp.oddhobb.com` | MCP endpoint (`/mcp`) | CNAME + ingress live — see `docs/mcp.md` |

All hosts currently serve the **same app**; the host only picks the opening
section. When a category deserves its own app (cards flow, my/roster), split
by pointing that ingress at a different local port — DNS and records stay put.

## Adding a section later

1. Add to `SECTIONS` in `backend/config.py` (id/label/icon/panel/host).
2. Map products in `SECTION_OF`.
3. If it gets a subdomain: `POST` the CNAME (mirroring the table) + one
   ingress entry + seamless cloudflared roll-over (start new connector,
   verify 4 registered, kill old — zero downtime, done four times now).
4. No frontend change needed — rail, chips and routing all read the registry.
