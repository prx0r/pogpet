# SPRINT — read this first (current execution focus)

> Packs are the core. One pack per product, gates green, then cards sorted,
> then Prodigi personalised, then transformations on top. Simple P0 on top:
> you-as-Santa on wrapping paper. This file is the sprint contract — any
> agent starting work here reads this before touching anything else.

## P0 order (do in this order, don't skip)

1. **One pack per product.** Every live product exists only as
   `catalog/packs/<SKU>/`. Current: 13 packs, 1 PRINT_READY
   (`FIG-PETBIG-TUX-80`), 12 DRAFT. Gate: `validate_pack.py --preflight`
   → LISTABLE. Biggest blocker shelf-wide: G07 real supplier quotes.
2. **Cards sorted.** Working end to end (6/6 Dad shelf, £2.99, Shopify
   invoice proven 2026-10-10). Remaining: Christmas recipes (shelf
   honestly empty), `test_delivery` drift fix, FAL title-art key.
3. **Prodigi personalised.** WRAP SKUs live-quoted (50×70 £14.99,
   75×90 £19.99, roll £24.99). Next: `wrap_repeat` renderer + tile for
   `wrap_pet_santa_repeat_v1` (draft recipe + santa prompt already seeded).
4. **Transformations on top.** `transforms/*.json` + `transform()` +
   capability router exist; 8 tests green offline. Light up in order:
   Higgsfield key → Soul ID for Dad → Marketing Studio heroes. Paid paths
   stay FAIL-closed (no key, no bill).

## Engine map (what runs where)

- **oddhobb.com** — storefront (cards, products, videos, studio tabs).
- **studio.oddhobb.com** — hardware engine (:8765, 18 tools), fronted by
  bridge token. Designs live in `studio/hwsim/designs/`.
- **mcp.oddhobb.com** — main agent surface (120 tools incl. 4 `studio_*`).
- Money truth: `catalog/STATUS.md` (packs), gallery shelf (cards),
  Shopify invoices (orders). Validator + receipts beat opinions.

## Don't

- List below LISTABLE. Ads below PROVEN. Estimates as costs.
- New surfaces before one physical pack hits LISTABLE.
- Touch `data/` caches (`cards/cache` keeps the shelf warm).

See also: `docs/todo.md` Round 14 (the 10), `docs/product-packs.md`
(standard), `vision/factory-interface-strategy.md` (doctrine).
