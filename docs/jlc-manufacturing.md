# JLC × OddHobb: manufacturing strategy (single brand)

Saved 2026-10-09. Owner decision: Grimoirer/Ochema/Glimlings fold
under OddHobb while testing. No separate brand identities until a
category earns one. Implemented as JLC_PROCESS + PRIMARY_SUPPLIER in
backend/config.py; Printie profiles stay for FDM lines.

## Processes (entry prices are JLC list, not landed cost)

WJP full-colour (from $5): people, pets, collectibles, minis. WJP
Tough (same band, walls >0.8mm): brick figures first — hair and
C-hands break first. SLA (~$1): sculptures, reliefs, decor. MJF/SLS
nylon (~$1): durable accessories, snap-fits, organisers. FDM (~$1):
PLA/PETG-style functional goods. BJ 316L ($5): talismans, jewellery
prototypes (polish optional, not jewellery-grade by default). SLM
steel/titanium ($8): premium structural. CNC ($5): tokens,
enclosures, instruments. Sheet metal (from $0.40): plates, tags.
PCB assembly: light-up/NFC/sensor products (flex 1/2/4-layer).

Landed cost ≠ list price: add polishing, deburr, hardware,
packaging, delivery. JLC is a production partner, not turnkey
personalised fulfilment — OddHobb owns QC, packing, shipping,
returns. No assumed dynamic one-off automation, branded packaging,
or mixed-material assembly without agreement.

## Line mapping (exact)

Brick figures → JLC WJP Tough multicolour (quote standard WJP
alongside). Ornament/keychain/croc/bag/brick-keychain → Printie
profiles (PLA display / PETG durable) until volume justifies JLC.
Cards/paper/CD → existing paper suppliers (never JLC). Coaster stays
non-wood: PETG profile, spec + photos already changed. Metal
engraving stays with current provider.

## Hard constraints (encode before checkout)

WJP: ~1mm min wall standard, no enclosed hollows; printed text
~0.4mm min coloured line; assembly ~0.2mm static clearance (moving
parts more). BJ metal: >1.5mm walls; distortion grows with size;
polishing removes precision interfaces. CNC UV/laser: artwork needs
size + placement. Flex PCB: component placement, bend radius,
moisture, battery protection engineered.

## Launch order

Alive miniature (£34.99 test) → engraved talisman (£39.99) →
math sculpture (£49.99) → NFC amulet (£59.99, passive tag first).
Glimlings/wearables only after simpler objects sell. First batch:
brick on WJP Tough, logo medallion on BJ-316L polished, 35mm alu
seal on CNC+laser, parametric object on SLA — real delivered quotes
anchor every family. Two processes carry the catalogue: WJP Tough +
CNC laser (minis, pets, gifts, amulets, medals, memorials).
