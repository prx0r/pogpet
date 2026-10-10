# Product packs — the only way a product goes live

> Source: `oddhobb-catalog-v1.zip` (coles' pack, imported 2026-10-10).
> Pack-authoring rules: `catalog/AGENTS.md`. Validator is truth.

## The definition

A **product pack** is `catalog/packs/<SKU>/` — one folder holding the print
file, its preflight proof, listing images rendered from that exact file,
listing copy, slot measurements, quote evidence, and `product.json`.
A product exists **only** as a pack. No pack, no product.

A product counts as finished **only** when this says LISTABLE:

```bash
python3 catalog/tools/validate_pack.py catalog/packs/<SKU> --preflight
python3 catalog/tools/build_graph.py   # rewrites graph.json + STATUS.md
```

| Level | Gates | Unlocks |
|---|---|---|
| DRAFT | failing G01–G06 | design work only |
| PRINT_READY | G01–G06 | supplier quote / test print for us |
| LISTABLE | G01–G13 | Etsy + oddhobb.com listing, customer orders |
| PROVEN | G01–G14 (needs a received physical sample) | paid ads, bundles, wholesale |

Current shelf (2026-10-10): 12 DRAFT, 1 PRINT_READY
(`FIG-PETBIG-TUX-80`). `CHARM-CROC-PET` reads PRINT_READY in
`STATUS.md`/`graph.json` but the validator says DRAFT — it is missing
`listing/`. Validator wins; rebuild the graph after fixing packs.

## What agents generate from a pack

- **Etsy listing**: `listing/*.png` (≥5, ≥2000px, hero + angles, all
  rendered from the print file) + `listing/listing.txt` (title ≤140 chars,
  13 tags, materials, ≥200-char description). No separate copywriting.
- **OddHobb shelf**: `product.json` (price, slots, audience) + `preview/`
  plates. Same files, no re-shoots.
- **FAL store standard** (own spec, mirrors G11): every listing image is a
  2000px PNG rendered from the pinned print sha, never from a design mesh;
  `listing/renders.json` is the provenance receipt. FAL/ads inputs reuse
  these exact images — one render set feeds store, FAL, and ads.
- **Ads**: only at PROVEN. Same images, same copy, spend on what sold.

## The dependency graph (where routing comes from)

```
suppliers.json → packs/<SKU>/product.json → templates (TPL-*)
      ↓
graph.json (nodes: supplier/template/product; products carry
            occasions/interests/slots/level)
      ↓
STATUS.md (the shelf at a glance)
```

Cards link in one layer up: recipes (`recipes/`) match on
occasion + photo count today; pack products carry the same
`occasions`/`interests`/`slots` vocabulary, so the matcher can rank
packs the way it ranks card recipes. That is the next wiring:

1. Read-only pack API for agents (`/api/packs`, `/api/packs/<SKU>`)
   serving `product.json` + listing images + level.
2. Matcher ranks LISTABLE packs per person (occasions/interests/slots).
3. Compiler personalises the top pack the way it compiles a card.
4. Routing/inheritance (packs referencing packs, shared templates,
   print-on-order fan-out) falls out of `graph.json` edges.

## Hard don'ts (from catalog/AGENTS.md)

- Never upload anything but `print/<SKU>-<process>.zip` of a PRINT_READY pack.
- Never list below LISTABLE. Never run ads below PROVEN.
- Never hand-edit `gates.json`, `listing/renders.json`, `print/preflight.json`.
- Any print-file change invalidates G03/G04/G05/G11: re-preflight, re-render,
  re-register. Listing photos can never drift from what we print.
