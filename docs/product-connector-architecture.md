# Product connector architecture — every SKU split into standard base + personalised top

Principle (from the Jibbitz/cribbage work): the mechanical interface NEVER
changes; only the decorative top is personalised. `Conf=YES` rows are the
confirmed rollout priority. Margins are Price minus Cost as listed.

## 3D-printed products (MAKR3D)

### KEYCHAIN-BRICK — $9.99 / $1.75 → $8.24 ✅ confirmed, active
- **Connector:** standard split-ring + chain + brick-stud base plate (one
  locked STL, 4.8 mm stud pitch to match the brick system).
- **Top:** personalised brick figure / printed face tile.
- **Next:** measure + freeze the stud-base STL as canonical.

### KEYCHAIN-COUPLE-BRICK — $12.99 / $3.37 → $9.62 ✅ confirmed, draft
- **Connector:** 2× standard keychain hardware + dual-stud base.
- **Top:** two personalised figures (couple/wedding).
- **Next:** same stud-base family as KEYCHAIN-BRICK; one base serves both.

### CHARM-CROC-JIBBIT — $7.99 / $1.75 → $6.24, active
- **Connector:** JACAD commercial Jibbitz connector STL
  (12.0 × 6.5 × 12.0 mm, ~$1.44 licence, owner to download).
- **Top:** any Meshy/custom model resized to ~25–30 mm, flattened rear,
  boolean union to connector; single joined PETG mesh (flex for insertion).
- **Next:** first product to ship the pattern end-to-end (Etsy 4587938701).

### KEYCHAIN-PET — $9.99 / $1.75 → $8.24, active
- **Connector:** standard split-ring + chain + topper cup (10 mm, same cup
  as the peg mount — one cup geometry reused).
- **Top:** mini pet bust (photo → mesh pipeline).
- **Next:** share the cup STL with XMAS-3D-CRIBBAGE-PEGS.

### BOARDGAME-PIECES-SET — $16.99 / $5.00 → $11.99, active
- **Connector:** standard 12 mm weighted base + 8 mm socket (one STL; pieces
  must stand on any board, same logic as the Jibbitz base).
- **Top:** personalised piece toppers (pets, initials, themes).
- **Next:** freeze base/socket STL; Etsy 4588020270 is live so this is
  revenue-facing — do it right after the confirmed three.

### XMAS-3D-CRIBBAGE-PEGS — $14.99 / $2.50 → $12.49, active
- **Connector:** proven taper shaft for 1/8" (3.175 mm) holes
  (liamriddell Easy-to-Print base, CC BY 4.0, owner to download;
  our `peg_topper_mount` is the same architecture as fallback).
- **Top:** pet bust on the 10 mm cup.
- **Next:** adopt downloaded taper as canonical shaft; print one sample
  in MAKR3D's material before listing (tolerances vary).

### XMAS-3D-ORNAMENT — $14.99, draft
- **Connector:** standard ornament cap + hanging loop (already in
  `wearables/` as `ornament_loop` hardware generator).
- **Top:** personalised bauble/figure (santa-hat dog pipeline proven).
- **Next:** ✅ confirmed — reuse the v4 dog+santa compose path.

### DICE-TOWER-WIZARD — $24.99 / $7.60 → $17.39, draft
- **Connector:** standard dice-chute core (fixed internal ramp angles +
  exit slot — the physics part that never changes).
- **Top:** wizard figure + themed outer shell.
- **Next:** highest margin ($17.39) but highest cost; freeze chute core
  first, shell is cosmetic.

### XMAS-3D-TILE-RACK — $12.99 / $3.37 → $9.62, draft
- **Connector:** standard tile groove rail (fixed groove width/depth for
  the tile set in use).
- **Top:** personalised rack ends (names, pet emboss).

## Digital products (no print connector — template + content)

Same split, different medium: locked template/canvas + personalised content.

- **ALBUM-MEMORY-CD** ($34.99/$2.00 → $32.99, KUNAKI): template = CD
  menu + chapter structure; content = customer photos/video.
- **ALBUM-WEDDING-VIDEO** ($59.99, draft): template = edit timeline +
  titles; content = wedding footage.
- **PROD-BOARDGAME-NOTEBOOK** ($16.99, draft): template = score-sheet
  layout; content = game/family names.
- **PROD-COASTER-SET** ($19.99, draft): template = coaster die spec;
  content = artwork per coaster.
- **PROD-PET-TAG-SET** ($16.99, draft): template = tag blank + ring hole
  spec (this one graduates to printed: metal/tag blank connector);
  content = pet name + artwork.
- **PROD-TOP-TRUMPS** ($24.99, draft): template = card layout + stat grid;
  content = photos/stats per card.
- **PROD-XMAS-PLAYING-CARDS** ($22.99, draft): template = 52-card +
  tuck-box dieline; content = photo faces.
- **XMAS-3D-CRIBBAGE-BOARD** ($29.99, draft): template = board hole grid
  spec (hole spacing/diameter lock with the peg shaft!); content = shape,
  artwork, inlay. **Pairs with the pegs — same hole spec both sides.**
- **XMAS-3D-FIRST-PLAYER** ($8.99, draft): template = token blank +
  stand slot; content = marker art.
- **XMAS-3D-MAHJONG-READER** ($11.99, draft) / **-WINDS** ($16.99, draft):
  template = tile/rack dims; content = faces.
- **XMAS-3D-TOKEN-TRAY** ($22.99, draft): template = compartment grid;
  content = dividers/labels.

## Flat print (PRODIGI — canvas spec + artwork)

- **POSTCARD-SET-CUSTOM** ($9.99/$2.00 → $7.99, draft): template = card
  size + bleed; content = photo collage.
- **STICKER-PACK-PHOTO** ($7.99/$0.80 → $7.19, draft): template =
  kiss-cut dieline; content = photo set.
- **WRAP-PHOTO-PERSONAL** ($12.99/$3.80 → $9.19, draft): template =
  wrap dims; content = photo repeat.

## Cross-product standard parts (print once, reuse)

| Standard part | Used by |
|---|---|
| JACAD 12 mm Jibbitz connector | CHARM-CROC-JIBBIT |
| 1/8" taper peg shaft | XMAS-3D-CRIBBAGE-PEGS |
| 10 mm topper cup | XMAS-3D-CRIBBAGE-PEGS, KEYCHAIN-PET |
| Split-ring + chain hardware | KEYCHAIN-BRICK, KEYCHAIN-COUPLE-BRICK, KEYCHAIN-PET |
| Brick-stud base plate | KEYCHAIN-BRICK, KEYCHAIN-COUPLE-BRICK |
| Ornament cap + loop | XMAS-3D-ORNAMENT |
| Dice-chute core | DICE-TOWER-WIZARD |
| Tile groove rail | XMAS-3D-TILE-RACK |
| Token/token-stand blanks | XMAS-3D-FIRST-PLAYER, XMAS-3D-TOKEN-TRAY |

## Rollout order

1. ✅ Confirmed three: KEYCHAIN-BRICK, KEYCHAIN-COUPLE-BRICK,
   XMAS-3D-ORNAMENT.
2. Live-revenue 3D lines: CHARM-CROC-JIBBIT, KEYCHAIN-PET,
   BOARDGAME-PIECES-SET, XMAS-3D-CRIBBAGE-PEGS.
3. Drafts by margin: DICE-TOWER-WIZARD, XMAS-3D-TILE-RACK, then digital
   templates (zero print risk, pure design work).
