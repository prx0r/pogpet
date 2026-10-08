# Hark MCP guide — cards (live 2026-10-08)

Connect: `https://mcp.oddhobb.com/mcp` with YOUR OWN key — header
`X-API-Key`, `?api_key=`, or the MCP `api_key` arg. Get one by signing up,
then mint a per-agent key (`POST /api/agents {name, permissions}` — ask
for `cards:read` to browse, `cards:create` to save/render, `cards:order`
to buy; keys show once, start read-only, revoke anytime). Keyed callers
land on the full tier already scoped to their owner — no shared token, no
other customer's data, ever. The master bridge token is operator-only; if
anyone sends it to you instead of a personal key, stop and ask. Owner for
beta: `hark-dad-a7a5cc` (Chris, father, golf).

## The one law

Display, don't generate. The site holds pre-vetted templates already
wearing the owner's photos. Your job is showing options, personalizing
words, and handing over proof URLs — never rendering card pixels yourself.
Anything you generate elsewhere becomes a product only after it passes
through attach-art below: validation, our renderer, export, payment. There
is no other road to print. Direct fulfil returns 410; checkout returns 409
until the current revision has a passing export render.

## Display (no design created)

- `figg_card_gallery({owner, subject_id})` — the Moonpig shelf: templates
  already wearing that person's confirmed photos. Scope to the active
  person; unknown people 404.
- `oddhobb_deal_cards({person, occasion, tone, signature, owner})` — four
  varied buyable cards in one call, four proof_urls. Signature required.
- `figg_card_reroll({design_id, owner, subject_id})` — same template,
  next photo set.

## Personalize (our renderer, our revisions)

- `figg_card_for_person({person, occasion, tone})` — zero-choice card,
  best portrait, profile headline.
- `oddhobb_make_card({subject_id, occasion, tone, signature, ...})` —
  canonical needs 4 confirmed photos; fullbleed (`template:
  "birthday_fullbleed"`) needs `front_art_url` or returns 409
  `art_required` — never a silent collage. Relationship label on live
  text ("Dad"), never the full name. Solo photos preferred.
- `oddhobb_edit_card_copy({design_id, headline, message, signature})` —
  new revision, art untouched. Caps 40/240/40.

## Outside art (yours in, validated)

- `oddhobb_attach_card_art({front_art_url (required, https, 5:7 ±2%),
  inside_art_url (10:7), back_art_url, headline, recipient, sender,
  inside_message, headline_baked (default true), art_source, prompt,
  owner})` — fetches server-side (15MB max, 800px short-edge floor),
  YuNet face presence on the front (flat rejects 400, illustrated
  near-miss warns), stores owner-scoped, mints a NEW revision, auto-renders
  preview + spread + export. Returns views, proof_url, triptych image.
- Keep baked words short and eye-QA the spelling: baked headlines can
  never be edited without new art. Message and signature are always live.

## Sell

- `oddhobb_checkout_card({design_id, revision, qty, idempotency_key})` —
  409 until export-ready, then ODD-CARD-5X7, £7.99, `product_url` +
  `checkout_url` (Shopify draft). Idempotency key required. Prodigi prints
  on `orders/paid` only — never before payment.

## Acceptance (run over MCP, report per docs/hark-beta-tests.md)

T1 make + proof, T2 one-call photo path, T3 copy edit loop, T4 schema
caps, T5 fulfil/checkout gates, T6 designed-lane smoke, T7 source/tier
honesty, T8 fullbleed attach lane. Report format: test, path, PASS/FAIL,
design_id, revision, proof_url, one line per view, exact error text.
