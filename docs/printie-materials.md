# OddHobb × Printie: material and product strategy

Saved 2026-10-09. Source: connected Shopify catalogue (15 drafts, GBP)
plus the two brick figures in production. Implemented as
PRINTIE_PROFILES + per-line printie_material in backend/config.py.

## Material selector (Printie)

Enable now: PLA (default/display), PETG (functional), TPU (flexible),
ASA (outdoor). Keep ABS + Nylon disabled until a product justifies
them. Fits Printie's guidance: PLA display, PETG tough/functional,
TPU flexible parts, ASA UV-exposed.

- PLA: figures, ornaments, game pieces, keycaps, charms, desk
  accessories. Cheap, detailed, indoor, multicolour.
- PETG: racks, clips, stands, keychains, trays, handled/dropped goods.
  Resilient, heat-tolerant.
- TPU: grips, cases, bumpers, sleeves, straps, non-slip feet, liners.
  The only flexible option — opens accessories PLA/PETG can't do.
- ASA: garden stakes, memorials, plaques, exterior mounts. UV-proof.
- ABS (later): heat-resistant indoor housings. Prefer ASA under UV.
- Nylon (later): hinges, snap-fits, joints, load-bearing mechanisms.

## Shopify 15 → Printie mapping

Christmas pet ornament → PLA (flagship, multicolour). Travel
cribbage board → PETG (handling; magnet assembly). Cribbage pegs →
PETG (validate peg + magnet dims). First-player token → PLA (cheap
custom). Mahjong reader → PETG (thin, smooth edges essential). Wind
markers → PLA (multicolour; PETG possible). Tile rack → PETG
(magnets/inserts). Token tray → PETG (functional candidate). Game
coaster → KEEP WOOD: listing promises wood; PETG means new spec +
photos, not a supplier swap. Metal pet tag → keep engraver (no
plastic equivalent). Top Trumps / playing cards / notebook / memory
CD / wedding video → paper/card/CD suppliers, not Printie. Brick
figures (separate) → multicolour PLA, never PETG.

## New product directions (concepts, not confirmed configs)

Alive character kits (PLA+PETG+TPU, figure + props + pedestal +
QR message; outfits later). Clog/shoe charms (PLA + TPU/PETG, fit
tested, collectible packs). Keychain/zipper charms (PETG+TPU, same
profile as desk figure/ornament/keychain). Game-night upgrades
(PETG+TPU trays, towers, racks, nameplates). Phone grips/cases
(TPU+PETG, device testing required). Outdoor decorations (ASA stakes,
markers, memorials).

## Architecture (implemented)

Customers never pick raw materials. Six manufacturing profiles
(Display/PLA, Durable/PETG, Flexible/TPU, Outdoor/ASA,
Heat-resistant/ABS, Mechanical/Nylon) map lines to Printie. One
personalised asset (mesh + texture + constraints) fans out to desk
figure, keychain, ornament, shoe charm, topper, magnet — each with
material + interface + validated print file — then Printie
manufactures and ships (approved files + SKU mappings; dynamic
one-off submission still needs verification before automation).
Launch order: multicolour PLA characters, PETG accessories, TPU
attachments. Printie takes painted 3MF; pricing covers material +
plate + colour + handling, shipping separate.

## Notes

Laura's figures: yellow faces/hands, brown hair, blue outfits
minimum; illustration detail needs separately validated colour
production.
