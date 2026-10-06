# OddHobb Roadmap — from stage one to the endgame

Companion to `thesis.md` (the MAKR3D-first one-shot manufacturing thesis).
This file is the product/shop roadmap: what we build, in what order, and where it ends.

## The endgame

> Personalised little things for people with oddly specific hobbies.

Upload your dog (or whatever) as a PNG → Meshy builds the mesh in the
formats we need → every product in the store populates with the active one —
figurines, charms, game pieces, stands — plus greeting cards. Then the people
layer: store Dad, sort his images, keep his birthday and a character profile,
and the shop starts working for you ahead of time. End state: auto-order, or
at minimum ChatGPT swiping through card ideas for you while you speak to it,
you confirm, it ships.

## Stage one (now): populate the store

Twenty Christmas listings, built from ~10–12 base files plus the active-mesh
personalisation engine. Bases come from the `data/3dprint` reference zips
(plus the existing chibi/brick meshes); every listing renders the customer's
active mesh/character. See "The Christmas 20" below.

## Stage two: mesh in videos, then make your own

Seeing the mesh in videos (the existing free video path: script + edge-tts +
still-frame render), then user-created variants — coat/hat/motif/name on top
of the approved body mesh, never a new mesh per variant. Studio customisation
stays controlled (registry IDs only).

## Stage three: digital downloads

Paid unlocks of renders/stills/turntables already rendered for free previews —
zero marginal cost, same pipeline, watermark off. Card print files and product
renders follow the same pattern.

## Stage four: the people layer (Dad)

Recipients table: person → birthday + notes + character profile → sorted
photos → occasions (birthday, Father's Day, Christmas) → card/product missions
per occasion. Autosort + rename flow is the seed; birthdays, profiles and
occasions are new.

## Stage five: agentic ordering

Card/product ideas generated per occasion from the recipient profile (swipe
feed), voice confirmation (STT still to wire — TTS-out works, mic-in doesn't),
then Shopify draft order. Draft-and-confirm first; per-recipient auto-order
only after trust is earned. MCP fullchain (`upload → mesh → personalise →
order(fulfil:true) → draft, no card charge`) is already live for agents.

## Q4 merchandising: Christmas is "Stocking Fillers" as the front door

Not the permanent definition of OddHobb — the Christmas merchandising layer:
*Personalised Stocking Fillers Under $15 / Game Night Gifts / Gifts for
Gamers / Gifts for Golfers / Gifts for Readers.*

Shop sections:

- **STOCKING FILLERS** — clog charm, bag charm, keychain, keycap, shoelace
  charm, book holder, golf marker, tumbler charm, cribbage pegs.
- **GAME NIGHT GIFTS** — Mexican Train station/racks, Mahjong pieces, rummy
  rack, card holder, cribbage.
- **GAMERS & COLLECTORS** — controller stand, artisan keycap, TCG grail stand.
- **PERSONALISED CHRISTMAS** — ornaments + existing people/pet products.

Advertise six: clog charm (impulse), ornament (seasonal urgency), Mexican
Train station (niche differentiator), Mahjong line reader (trend), controller
stand (gamer gift), golf marker (evergreen). The rest gives depth, upsells,
search coverage, and tells us which ecosystem to expand.

Headline direction: **"Odd little gifts for the things they're obsessed
with."** Personalised game-night, hobby and stocking fillers from $7.99.

## The Christmas 20 (in order)

1. Personalised Clog Shoe Charm — $7.99–9.99 — PETG — stocking hero
2. Personalised Bag Charm — $9.99–14.99 — PLA/PETG
3. Custom Pet Keychain — $9.99 — PLA (already effectively ready)
4. Custom Brick/Person Keychain — $9.99 — PLA (already built)
5. Custom 3D Christmas Ornament — $14.99 — PLA (far along, Christmas hero)
6. Personalised Cherry-MX Artisan Keycap — $12.99–19.99 — PLA/PETG
7. Personalised Shoelace Charm Pair — $9.99–12.99 — PETG/PLA
8. Personalised Book Thumb Page Holder — $7.99–10.99 — PLA
9. Personalised Golf Ball Marker — $9.99–12.99 — PLA/PETG
10. Personalised Tumbler Straw Charm/Topper — $7.99–9.99 — PETG
11. Personalised Controller Stand — $19.99–24.99 — PLA/PETG (gamer gift hero)
12. Mexican Train Family Station — $19.99–24.99 — PLA (game-night hero)
13. Personalised Mexican Train Domino Racks — $24.99–34.99/set — PLA
14. Personalised Mahjong Line Reader — $9.99–12.99 — PLA
15. Personalised Mahjong Wind Indicator — $12.99–16.99 — PLA
16. Personalised 4-Tier Rummy Tile Rack — $14.99–19.99 each — PLA
17. Personalised Playing-Card Hand Rack — $12.99–16.99 — PLA
18. Personalised TCG "Grail" Card/Slab Stand — $14.99–19.99 — PLA
19. Personalised Cribbage Peg Pair — $12.99–16.99 — PETG
20. Personalised Dart Stand — $19.99–24.99 — PLA

Price ladder: $7.99–12.99 stocking fillers pull customers in; sets, stands,
four-player bundles and collector pieces push baskets toward $25–50+.

## Production matrix (to fill per listing)

Base mesh/reference → licence → dimensions → PLA/PETG → est. MAKR3D cost →
personalisation method → listing price → sample needed/not needed.
Rule: every new base gets one real MAKR3D sample before listing.

## Post-Christmas probes

Disc golf, pickleball, AirTag shells, wine-glass charms, stethoscope tags,
knitting/crochet accessories, snow-day toys, fishing, geocaching.
