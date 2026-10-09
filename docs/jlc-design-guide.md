# JLC design constraints (imported 2026-10-09)

Sources: JLC3DP design guide (blog/how-to-design-3d-models-for-printing),
WJP product page, Full Color Tough Resin article. Full text upstream;
numbers below are the enforceable subset. Implemented as
JLC_CONSTRAINTS + jlc_check() in backend/config.py.

## Per-process table

| Process | Min wall | Clearance (moving) | Tolerance | Supports | Notes |
|---|---|---|---|---|---|
| FDM | 1.2mm | 0.5mm | ±0.3mm ≤100mm | >45–60° | Holes print small; Z weakest |
| SLA | 0.8mm | 0.5mm | ±0.2mm ≤100mm | resin-specific | Drainage holes for hollow volumes |
| SLS/MJF | 1.0mm | 0.6mm | ±0.3mm ≤100mm | none (powder) | 1mm min channels, escape holes |
| Metal SLM | 1.5mm | 1.0mm | ±0.3mm ≤100mm | required, hard removal | Radii not sharp corners |
| Metal BJ | 1.5mm | 1.0mm | ±0.3–0.4% ≤50mm | none | 10–15% sinter shrinkage; machining stock |
| WJP full-colour | 1.0mm | 1.5mm | ±0.2mm ≤100mm | support material | Matte finish; 600×600×1200dpi |
| WJP Tough | >0.8mm | 1.5mm | ±0.2mm ≤100mm | support material | 30–50MPa tensile; HDT 50–55°C; no sun, no metallic |

WJP product limits: build 380×330×230mm (tough 390×340×240), min
feature 5×5×5mm, emboss/engrave ≥0.8mm deep+wide, assembly clearance
0.2mm static, threads 1.5mm. Tough: 72h+ build, slight colour
variation, fades in sun.

## Universal rules (all processes)

Design walls with margin above minimum, not at it. Floating geometry
is a fail. Mating parts need designed clearance (same nominal =
interference). Chamfer 45° instead of horizontal ledges. Flat stable
base or explicit raft. Hollow SLA needs drainage. Verify mm scale
after every export. STL fine mesh: chord 0.01–0.02mm, angle 1–2°.
Snap-fit arms ≈5× thickness, flex axis on strong layer direction.
FDM holes: oversize 0.1–0.2mm.
