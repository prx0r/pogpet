# How it all works — and the organised way to build it

> Written 2026-09-30. This is the **map**: what the system is, why the
> approach is contract-first, why `my.oddhobb.com` is the centre, and which
> doc answers which question. Read this first, then the doc map below.

## The one-sentence system

A customer gives us a photo on **my.oddhobb.com**; we turn it into a mesh;
**every product in the catalog then previews with *their* pet**; they buy the
ones they want (cards, gifts, prints); an agent can do all of it for them
through **MCP**.

## The organised approach: contracts first, pages second

The mistake available to us is building three surfaces (site, subdomains,
agent) that each learn a different version of the truth. The antidote is
already half-built — do it deliberately:

```
             ┌──────────────── registries (backend/config.py) ────────────────┐
             │ SECTIONS · SECTION_OF · PRODUCTS · PRODIGI · emoji/blurb       │
             └──────┬──────────────────┬───────────────────┬─────────────────┘
                    │                  │                   │
        GET /api/catalog, /api/flow, /api/sections    MCP manifest (figg_*)
                    │                  │                   │
             ┌──────▼──────┐   ┌───────▼────────┐   ┌──────▼─────────────┐
             │ my.oddhobb  │   │ oddhobb.com +  │   │ Muse agent          │
             │ (the flow)  │   │ category hosts │   │ (ChatGPT/Claude/…)  │
             └─────────────┘   └────────────────┘   └────────────────────┘
```

**Rule of thumb:** if a fact appears in code twice, it belongs in a registry;
if a capability appears in the UI but not in MCP (or vice versa), the contract
is broken — fix the contract, then the surface. Docs in this repo describe the
contract, not screenshots.

Build order (how I'd sequence everything from here):

1. **Contract** — MCP design + registries *(done for now: `docs/muse-mcp-design.md`)*
2. **The flow page** — `my.oddhobb.com` as the human mirror of the contract
   *(routing works today; the page UX is the next build)*
3. **The rubric** — the trust gate before money moves (vision §4)
4. **Orders** — the actual hole in the contract (`figg_order` + checkout)
5. **Depth** — category content, voice, Amazon-grade browse

## `my.oddhobb.com` — why it's the most important page

It is step 1–5 of the entire product. Everything else is downstream:

1. **Upload** — one photo, drag-drop, the QC we already have (`intake`: magic
   bytes, EXIF, ≥256 px, flat-frame reject, dedupe) should surface as friendly
   guidance *before* the file is rejected (rubric preview).
2. **Flow states** — the page renders exactly what `GET /api/flow` returns:
   `empty → uploaded → sculpting → ready`, each with the server's `hint`.
   No invented UX states: if the page shows it, the API said it.
3. **Spotlight/roster** — pick which pet is active; the active mesh is what
   every preview, card and (later) every browse view renders.
4. **Hand-off** — when `stage=ready`, the page's job is to walk them to the
   previews ("21 products now feature Nibble") — the shop is a *continuation*
   of this page, not a separate destination.
5. **Identity** — this is where `handle`/`api_key` are created (`claim_owner`
   adopts the anonymous profile so nothing is lost).

Design constraint: this page must never require understanding what a mesh is.
Photo → progress → "here's your pet on everything."

## The sample pet

The system ships with a real one: owner **`anon`** (the default for logged-out
visitors) holds the **generated dog mesh** and its premesh-normalised PNG,
bound to all 8 mesh products and set active — so every first visit renders a
populated roster, shop and previews with zero setup. Seeded by
`scripts/seed_sample.py` (idempotent, 0 credits). And because of the
inheritance guarantee (`docs/foundation.md`), **any product we add later
appears on it automatically** — that's the flow: add product → every mesh
inherits it → previews update.

## The stack (what talks to what)

```
browser ── https://oddhobb.com (any subdomain)
   └─ Cloudflare zone + named tunnel (figgsite.yml ingress → host routing)
        └─ bridge :8797   static site, /studio, /premesh, gated /backend proxy, gated /mcp
             ├─ Flask :8798   44 routes: intake → mesh jobs → products → stage → print
             │    ├─ sqlite (data/figg.db)  ├─ R2 via rclone (artifacts)
             │    ├─ Meshy API (credits — ask first)  └─ Prodigi (quotes/print)
             └─ MCP  :8799   127.0.0.1 only, manifest-driven tools (Muse contract)
```

Local-only: MCP (never public directly — its tools carry the service token),
data/ (photos, meshes, ledger). Public: everything the bridge gates with the
one client token.

## Doc map (which file answers what)

| Question | Read |
|---|---|
| Where are we going, product-wise? | `docs/oddhobb-vision.md` |
| **How does it all fit together?** | **this file** |
| How do I add a product/tool/section? | `docs/foundation.md` |
| Why subdomains/rail/routing work like this | `docs/navigation.md` |
| How does an agent connect to the MCP? | `docs/mcp.md` |
| **How should MCP evolve (Muse-first)?** | `docs/muse-mcp-design.md` |
| What does Meshy cost / spend rules? | `docs/meshy.md` |
| How does a product hang/balance/print? | `docs/balance.md` |
| How do we render sellable images? | `docs/rendering.md` |
| What are we building next? | `docs/todo.md` + `HANDOVER.md` |
| What's the weird local state? | `AGENTS.md` (rules) → `HANDOVER.md` |

## Working agreements (short list)

- **Ask before money** — Meshy credits, any paid API (AGENTS.md money rules).
- **Registries own facts**; pages and agents only present them.
- **Contract first** — new capability lands in MCP + API together, or not at all.
- **Docs next to code** — `docs/` in this repo, updated in the same commit
  as the change (we don't have commits yet — first one will carry all of this).
