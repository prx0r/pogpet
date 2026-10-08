# OddHobb Cards — the one-pointed vision

> **Every card is a frozen, buyable thing: a front, an inside, and a back,
> personalised from someone you love, at a fixed £7.99, printable exactly
> as previewed.**

That's the whole product. Everything below is a consequence.

## What this rules in

- **The card is the product, not the picture.** A preview alone is never
  done. Done means a `card_url` whose revision renders, passes preflight,
  and returns a `checkout_url` a human can pay at.
- **One revision, one truth.** Every edit (text, font, crop, template) mints
  a new immutable revision. Checkout always buys the revision you're looking
  at. Orders reference frozen revisions, never live state.
- **Renderer owns geometry; people own words.** The AI (or human) chooses
  template, photo, crop, words, and font *ids*. Coordinates, bleed, DPI,
  panel order, and the back brand mark belong to the deterministic renderer
  and have no inputs by construction.
- **Controlled custom, everywhere.** Fonts, like coats, come from a small
  curated registry clustered by vibe and occasion — pick an id, never a
  file. Contrast always holds because colours are semantic per template.
- **Agents and humans share one surface.** Same specs, same revisions, same
  previews, same checkout — whether the hands are chat tools or the editor
  page. `via` records which path made each revision.
- **Money has one boundary.** OddHobb owns what is being made, Shopify owns
  whether it's paid for, Prodigi owns making it. No print before `orders/paid`.

## What this rules out

- Free-form fonts, colours, or layouts (print-unsafe, unquotable).
- AI-generated typography inside scene plates (fal.ai plates are text-free;
  all words are real renderer-owned type).
- New Shopify products per card (one hidden SKU, personalisation rides as
  line-item data, source photos never leave us).
- Browsing a second Shopify storefront (Shopify is checkout + ledger only).

## The normal user workflow (what we converge on)

```
Dad (profile: golf, dry humour, birthday)
  → 3–5 card variants from his photos (agent or gallery)
  → human picks one card_url
  → open it: front / inside / back
  → edit inside message together, pick fonts by vibe
  → new revision + fresh preview each edit
  → Buy £7.99 → Shopify checkout → paid → Prodigi prints it
```

## How an agent chooses fonts (basic version)

Each registry font carries `vibes`, `occasions`, and `use_for`
(headline / name / body / accent). Match the brief's tone and occasion
against `vibes`/`occasions`, keep the slot's `use_for` role, and fall back
to `fraunces` headlines + `inter` body when nothing matches. `figg_card_fonts`
returns the whole table; no other font knowledge is needed.
