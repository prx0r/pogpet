# Base contracts audit — 2026-10-08 (measured, not claimed)

Measured every `scripts/factory/adapters/*.json` master with a 50-byte-stride
STL parser (the 48-byte stride reads garbage — ASCII/binary sniffing also
lies; verify with Blender, not cleverness).

## Emboss pipeline: FIXED this round

`personalize.py` placed text at the adapter's raw z, which had drifted from
the masters — text ended up buried inside the part and UNION added zero
faces while returning success. Golf CHRIS: 1,788 faces in, 1,788 out.
Now: text centered in mesh space, XY from adapter origin, Z from the
MEASURED base top along the face normal, and the run REFUSES (exit 3, no
file) unless vertex count grows. Golf CHRIS now 1,788 → 4,400 faces.
Book MARGARET and croc TOM verified growing too.

## Per-line verdicts

| Line | Master dims (mm) | Contract | Verdict |
|---|---|---|---|
| golf_marker | round dia 24, 3.1 thick, floats z -1..2.1 | thickness 2.0, flat top ±0.2 | MISMATCH — needs product decision: remodel master to 2.0 (re-render stills, re-sample) or re-contract to measured. Do not touch unilaterally. |
| croc_tag | pin dia exactly 4.20 in z 1–4.5, face z 0–1, head to 5.2 | stem lock dia 4.2 | CORRECT. Reported 5.74 came from an agent upload, not the master. Validator rightly flags uploads. |
| brick | serves `/img/prod/brick-figure.glb`; tile stills were dog photos | brick imagery | FIXED: rendered brick hero/front/side/back (+loop=hero); tile now 100% brick. |
| keycap/book/croc/clog/straw/wind | placement was adapter-z blind | face-top placement | FIXED by measured-top placement (same code change as golf). |
| card racks/slab/tcg (+Y normals) | unchanged path (adapter origin kept) | — | Unchanged; verify per-line on first real make. |

## Rules going forward

1. Adapters own XY intent; Z placement is always measured from the base.
2. A make that adds no geometry is a failure, never a 200.
3. Masters vs contracts: measure both, change the file only with a sample
   plan attached. `dims_mm [24,12,24]` matches reference orientation.
