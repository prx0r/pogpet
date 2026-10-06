# OddHobb — product vision

> Captured 2026-09-30 from the founder's description, near-verbatim where quoted.
> This is the direction document: **the site we already built (on the
> petsy/bwick base, live at pog.pet) becomes OddHobb.** Decisions here drive
> the build order; keep it updated as decisions land.

## The reframe, in their words

> "I'm imagining it like **Amazon** tbh but with **chat bar at the bottom**…
> we still have our personalised flow — 'what odd thing shall we make you?'…
> and **you can speak into it**… we still do our **card personalisation**…
> the `my` is where u upload your photos / assets, and then when you're
> browsing **you're always looking at your custom version of the things**."

So: an **Amazon-style catalog where everything you look at is already yours**,
with the maker-chat always docked at the bottom and voice as an input.

## The six pillars

### 1. Browse like Amazon, talk like a pet
Catalog-first layout (categories, product grid, the depth Amazon implies) with a
**persistent chat bar docked at the bottom of every view** — not a tab you open.
The existing personalized flow stays: the host asks *"what odd thing shall we
make you?"* and the whole conversation happens in that bar.

### 2. Voice in
"you can speak into it" — speech input on the chat bar. Start with the
**Web Speech API** (free, on-device in Chrome/Edge; graceful fallback to typing),
evaluate paid STT only if quality/coverage demands it.

### 3. Personalized-by-default browsing
"when ur browsing you're always looking at your custom version of the things."
Every product card, listing and preview renders **your active mesh** — the
mechanism already exists (shop cards render `source_kind: mesh`, spotlight
propagates the active mesh) but it must become the *default everywhere*, with a
clear "your version" affordance and a way to switch which pet you're shopping
as (the `my.` space supplies the roster).

### 4. The rubric — "a custom rubric to see if we can make it"
Before any credits or promises: assess the upload against a **makeability
rubric** and tell the user the verdict in chat — *we can make this / re-shoot
with X*. Start rule-based on the signals intake already computes (size, flat
frame, EXIF, dedupe) plus subject checks; layer model judgment later. This is
trust infrastructure: it stops bad uploads at the door instead of after a
failed mesh.

### 5. Card personalisation continues
Cards are a first-class line → **`cards.oddhobb.com`** (flow, Prodigi SKUs and
`/api/listing-pack` already exist for the Etsy side).

### 6. `my.oddhobb.com` — your asset space
Upload photos/assets, see your roster of pets/meshes, choose the active one.
Today's owner id + `localStorage` + upload route are the seeds; this is where
the identity lives so browsing can be personalized everywhere else.

## Domain map

| Host | Role | Infra |
|---|---|---|
| `oddhobb.com` / `www` | catalog + docked chat (the store) | ✅ zone + NS pending, CNAME + ingress live |
| `my.oddhobb.com` | asset upload / roster / identity | ✅ CNAME + ingress live (same app until split) |
| `cards.oddhobb.com` | card personalisation flow | ✅ CNAME + ingress live (same app until split) |
| `pog.pet` | existing alias — redirect or keep? | 🟡 open decision |

## Exists vs gap

| Pillar | Already built | Missing |
|---|---|---|
| Catalog | shop grid, 13 products, mesh-rendered cards, spotlight switch | Amazon-grade IA: categories, search, sort/filter, depth; **always-my-mesh default** across views |
| Chat | AI host persona (CAST), chat tab, `"what odd thing shall we make you?"` flow | **Docked bottom bar on every view**; voice input |
| Rubric | intake QC (magic bytes, EXIF, ≥256 px, flat-frame, dedupe) | Makeability verdict + reasons surfaced in chat *before* spending credits |
| Cards | card product, Prodigi path, listing-pack | `cards.` host + flow isolation |
| `my.` | owner id, upload route, localStorage roster | `my.` host + roster/gallery UI, mesh switcher |
| Brand | copy/title swapped to oddhobb (7 subs), NS pending | og/meta tags (none exist), mascot decision, PUBLIC_BASE |

## Proposed build order

1. **Docked chat bar + voice** — highest-visibility change, reuses the existing
   chat stack; Web Speech API for input, typed fallback.
2. **Personalized-by-default browsing** — make every catalog view render the
   active mesh and say so ("this is your {pet}"); roster switcher in the bar.
3. **The rubric** — rule-based makeability verdict wired into intake, shown in
   chat before generation; model-judged rubric later (see `docs/meshy.md`
   money rules if it ever costs credits).
4. **Subdomain split** — `my.` and `cards.` are live at the edge already;
   split the apps behind them when the flows diverge (until then they serve
   the same app).
5. **Amazon depth** — categories/search/sort/reviews as the catalog grows.

## Open questions

1. **Rubric scope** — photo-readiness ("can we make *this photo*?") as read
   here, or product-level ("can we make *this thing*")? Both are useful; which
   is the first version?
2. **Voice** — Web Speech API (free, Chrome/Edge, typed fallback) acceptable,
   or do we want paid STT day one?
3. **pog.pet** — 301 redirect to oddhobb.com, or permanent alias?
4. **Mascot** — still named "Pogo" (5 copy lines + AI persona). On-brand or
   rename?
5. **Amazon-like depth** — how far does the analogy go (categories, search,
   reviews, subscribe-style reorders)?
