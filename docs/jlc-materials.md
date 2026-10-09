# JLC materials bible — every material, every process, with prices

Saved 2026-10-09 from JLC's own pages (raw snapshots in
`~/supplier-docs/jlc*`). This is the reference AI designs against: pick a
material → check the design table → read the price basis → know the order
path. Machine twin: `backend/jlc_materials.json`.

Price truth: JLC publishes **no CSV, no price database, no open price API**.
Unit pricing lives behind the instant-quote engine (upload-gated) and moves
— July 2026 cut six materials 9–70%, May 2026 raised CNC on tungsten +
aluminium costs. Anchors below are last-published with dates; everything
else resolves at quote time. The quote itself is the API
(`docs/fulfilment-automation.md`).

## JLC3DP — 3D printing (7 processes)

Quote rules (all processes): STL/STP/STEP/OBJ/3MF, wall >1.2mm,
thinnest feature ≥0.8mm. ISO 9001.

| Process | Materials (orderable now) | Build mm | Tolerance | Build | From |
|---|---|---|---|---|---|
| SLA resin | 9600, 8001 (+transparent 8001), Black, Imagine Black, 8228, LEDO 6060, CBY, JLC Black, Grey, JLC Temp, 9000HE, X | 780×780×530 | ±0.2mm / 0.3% | 2d | ~$1 |
| WJP full-colour | Full-Color Resin, Full-Color Tough Resin | 380×330×230 (Tough 390×340×240) | ±0.2mm / 0.3% | 24h–72h+ | $5 |
| SLS nylon | 3021PA-F*, 3301PA, 3401GB, 1172Pro (*listed as 3201PA-F in one JLC page — verify code at quote) | 350×350×400 (1172Pro 250×250×590, 3401GB 340³×400) | ±0.3mm / 0.4% | 2d | ~$1 |
| MJF nylon | PA12-HP, PA12S-HP, PA11-HP, PAC-HP | 370×276×360 (PAC-HP 320×175×225) | ±0.3mm / 0.4% | 2d | ~$1 |
| FDM plastic | ABS, ABS-ESD, ASA, PLA-P, PA12-CF, PEBA, TPU, PEEK | 580×480×480 (ABS/PA12-CF/PEEK); 250³ (ABS-ESD); 250×250×300 (ASA/PLA-P/TPU/PEBA) | ±0.3mm / 0.4% | 3d | ~$1 |
| SLM metal | Titanium TC4, 316L stainless | 390×290×390 | ±0.3mm / 0.4% | 3d | $8 |
| BJ metal | BJ-316L | 100³ | ±0.3mm/0.4% ≤50mm, ±1.3% above | 5d | $5 |

Published $/g anchors (ex-tax): **MJF-PA12 $0.275/g, SLM-316L $0.21/g**
(Aug 2025). July 2026 cuts (no absolutes given): PAC-HP −70%, TC4 −47%,
PA12-CF −24%, PLA-P −18%, Full-Color −11%, ABS −9%. Black-resin sanding
+15–20% (manual labour).

OddHobb mapping: brick → WJP Tough (hair/C-hands break first, walls
>0.8mm, no enclosed hollows, no sun); game pieces/snap-fits → MJF/SLS
nylon; flexible charms/clips → FDM TPU; outdoor → FDM ASA; talismans →
BJ-316L (detail ≥1mm, 10–15% sinter shrink, polish optional); premium
structural → SLM.

## JLCCNC — machining + laser

Metals: aluminium 6061/7075, brass H59, copper T2, stainless SUS304, steel
alloy 45#. Plastics: ABS, FR4, Nylon-PA6, PC, PMMA, POM, Bakelite. No
titanium, no ultra-tight work (their words). Milling 3/4/5-axis + turning,
tolerances ISO 2768-m / ±0.1 / ±0.05 / ±0.02. Laser cutting (Al, stainless,
steel alloy) from **$0.40**, 2 days, ±0.2mm. CNC from **$5.00**, 3 days.
Final price subject to manual review; instant quote is reference-only.

OddHobb mapping: 35mm alu seal (CNC+laser — owner call vs current
engraver), discs/plates/housings, precision fits, sheet tags.

## JLCPCB — boards + assembly

Rigid FR-4 1–32 layers (Grade A Nan Ya/KB/Shengyi), 0.4–2.0mm, 1–2oz
outer, finishes HASL/lead-free/ENIG/OSP, 4/4mil trace-space (1-2L 1oz),
max 670×600mm (2L to 1020×600). Flex 1–4L (PI 25/50µm, transparent PET,
stiffeners PI/FR4/steel/3M tape) — **no rigid-flex**. Also alu/copper
core, Rogers/PTFE. 2-layer prototypes from **$2/5pcs** (headline, not
landed — shipping dominates; see comparepcb.com).

Assembly: Economic (2–50pcs, 0402 min, $8.18 setup, $0.0016/joint, $1.53
stencil) / Standard (to 80k pcs, 0201/01005, 0.35mm pitch). Hand-solder
$3.50/order. Parts library 40k+ kinds (698 basic + 300k extended) plus
global sourcing — design around stocked parts. 4–5 days fab+assemble.

OddHobb mapping: Glimlings/Muse core (BLE MCU, LEDs, haptics, IMU, NFC,
LiPo on flex), NFC amulet inlays, any sensor wearable. Phone holds AI
first; no always-listening hardware.

## What AI must never invent

Per-part $/g for unanchored materials, landed totals (shipping+VAT move
per country — comparepcb.com proves 2–3× spreads on the same board),
lead times (capacity-linked), and post-processing fees. Quote or mark
QUOTE. Refresh this file when JLC posts a pricing news update.
