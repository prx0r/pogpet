# Factory mapping: breath-sensor prototypes A/B/C

Saved 2026-10-09. Vision: `docs/stone-breath-sensor.md`. Question: what can
the factory make, what must be procured, and what is out of scope? Short
answer: all mechanics + all PCBs + all assembly are in-lane at JLC; sensors,
cells and tubing are procured components; micro-MEMS is literature-only.

## Prototype A — thermistor bridge (build first)

| Component | Route | Lane + price basis |
|---|---|---|
| Bridge mount + 2 tips (~30×15×10mm) | MAKE — JLC SLA (8001 / JLC Black, smooth, tiny) | ~$1 floor; gates: walls ≥0.8mm, tip columns ≥1.0mm, holes ≥1.0mm (`factory_analyze` vs SLA) |
| Sensor board | MAKE — JLCPCB rigid 2L for rev 1 ($2/5pcs headline), flex 2L PI for the comfort rev | rigid first, flex when worn daily |
| Assembly | MAKE — Economic PCBA ($8.18 setup, $0.0016/joint, $1.53 stencil; NTCs + passives + LiPo conn + USB-C; BLE MCU QFN at 0.4mm+ pitch fits Economic) | ~$10 + components |
| NTCs, BLE MCU, LiPo cell | PROCURE — LCSC/JLC parts library (live stock+pricing via jlcpcb-mcp, no creds) | verify assembly-stock, not retail-stock |
| Firmware + breathing engine | SOFTWARE — DeityBody side, not factory | BLE stream, on-Stone rendering |

First-rev sketch (landed, verify at quote): SLA $1–3 + 5 PCBs $2 +
assembly ~$10 + components $5–15 (MCU dominates) + shipping $8–15 → roughly
$25–40 for five sensor boards with mounts. Skin-contact caveat: standard
SLA resins carry no skin certification — limit prototype wear time, find
the biocompatible path before any daily-wear rev (same honesty rule as the
316L jewellery warning).

## Prototype B — pressure cannula (parallel)

Cannula tubing: PROCURE (medical consumable, don't manufacture). Pressure
transducer (e.g. Sensirion SDP / NXP MPX class): PROCURE as component,
mount on a breakout PCB + Economic assembly (same lane as A). Enclosure:
MAKE, SLA. Everything else identical to A. B costs one extra breakout
board and the transducer itself.

## Prototype C — hot-film micro airflow (don't build)

Custom MEMS is outside every lane we have. Verdict: literature-only until
A/B justify it. Validation rig instead: respiration belt (procure,
accuracy benchmark) + Sensirion eval-kit reference sensor (procure) +
mouth-breathing flag in the engine.

## Stone side (same lanes)

Transparent 8001 diffuser (SLA transparent resin exists in-lane), flex
2–4L PCB, Economic/Standard assembly for LED/BLE/haptic drivers,
enclosure SLA or WJP. No new supplier needed.

## Factory tool coverage today

`factory_analyze` ✓ (mount vs SLA gates), `factory_estimate` ✓ (Resin
lanes rank; JLC SLA floor applied by hand), `factory_catalog` ✓ (SLA
resins, flex stackups), parts search ✓ (jlcpcb-mcp, live, no creds),
`factory_quote` ⏳ (JLC pricing approval), `factory_order_*` ⏳ (gated).
Sequence: analyze mount STL → estimate → quote (post-approval) → 5×
rev-1order → validate against belt + reference → comfort rev in flex.
