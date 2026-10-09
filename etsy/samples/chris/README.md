# OddHobb Etsy samples: Chris set (2026-10-09)

Each product starts from its site template (GET /backend/api/design/base/<line>, saved in masters/) and keeps that template's locked interfaces. The placeholder form is rebuilt around them. Every print file is watertight, 1 body (manifold3d).

| # | Product | JLC process | Size (mm) | Vol cm³ | Locked interface kept | Personalisation |
|---|---|---|---|---|---|---|
| 1 | Golf ball marker | CNC 6061 alu, black anodise, laser mark both faces | 24 x 2.0 | 0.83 | dia 24, thickness 2.0 | CHRIS / PAR IS OPTIONAL; back LOVE, THE KIDS, XMAS 2026 |
| 2 | Mahjong line reader | WJP Full Colour (jade + ivory) | 165 x 44 x 3.1 | 13.8 | reading window one card line | CHRIS, DAD'S TABLE - NO PEEKING, dot-tile icons |
| 3 | Card hand rack | MJF PA12 black, open-bottom shell 2.5 walls | 200 x 62 x 34 | 86.7 | 3 grooves 2.5 mm, length 200 | CHRIS engraved 1 mm + suits (gold paint-fill = hand finish) |
| 4 | Dart stand | MJF PA12 black | 110 dia x 53 | 64.8 | 3 bores 12.4 (12 + clearance) x 40 deep | dartboard relief, CHRIS / 180 CLUB banner, DAD'S DARTS arc (gold = hand finish) |
| 5 | Cribbage pegs | Binder-jet 316L, polished | 8.6 x 29.7 | 0.55 | shaft 3.1 mm x 14 (1/8" holes) | golf-ball pegs + flag pegs engraved CP |
| 6 | Artisan keycap | WJP Full Colour | 18 x 18 x 16 | 1.05 | Cherry MX female cross 4.15 x 1.32, 4.6 deep | 19th-hole green, flag, ball; CHRIS on front |
| 7 | Croc charm | WJP Full Colour (OBJ+MTL+PNG in out/p07_croc_charm/jlc/) | 26 dia x 11 | 1.92 | stem 4.2 mm, stopper 6.8, face <= 32 | cartoon Chris badge (generated art) |
| 8 | Keychain | WJP Full Colour | 45 x 26 x 46 | 11.4 | printed loop, ring hole 4.0 | Chris bust from his mesh + CHRIS plate |
| 9 | Xmas ornament | WJP Full Colour | 22 x 18 x 85 | 6.2 | printed loop hole 5.0 / wire 2.4 | Chris figure 72 mm + Santa hat |
| 10 | Mini-Me desk figure | WJP Full Colour | 46 dia x 73 | 16.9 | 75 mm class figure | Chris 66 mm on putting-green plinth, CHRIS |

## Notes
- Template issues found: dart_stand master is 10 mm tall but specs 40 mm bores. golf_marker master is 3.1 mm thick against a 2.0 contract. card_rack master is 180 long against the contract's >= 200. Line reader master is a flat slab. Keychain, ornament and brick serve the canonical dog GLB.
- For JLC WJP, the multi-part colour renders (8-10, 2, 6) still need one textured OBJ/3MF per product: either bake part colours into the Chris atlas, or export a colour 3MF. The croc charm package is already in that format.
- Pricing flags at JLC WJP (about $0.8/cm³ above the floor): the line reader (~$11) and mini figure (~$14) need higher list prices than config.py has. MJF rack and stand need real quotes.
- Scripts: g0N_*.py (geometry), r0N_*.py (render), studio.py, geo.py, props_tex.py. Finals are out/pNN_*.png.
