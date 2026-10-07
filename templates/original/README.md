# Originals — house cards you can just buy

Non-personalised OddHobb originals. No photo, no subject, no mesh needed:
pick one, buy it, done. Personalised remixes of the same premises live in
the other style families (`xmasaisketch`, `comicstory`, …).

Premise quality is the product here — see `docs/original-premise-bible.md`
(the full guide: formula, mechanisms, premise taxonomy, 20 seeds). Image
style is ~20% of why these work; the premise is the other 80%.

Premise families (first pass, from the bible):

- `elf_displacement` · `agent_overload` · `hallucination` · `slop_parody`
- `overoptimization` · `bureaucratic_christmas` · `rebrand_theatre`

Machine-readable seeds: `templates/premises/original_families.json`.
Catalog section: style `original` in `templates/catalog.json` — the Cards tab
renders it as its own rail automatically. Renders use the same editorial
sketch treatment as `xmasaisketch` (`backend/renderers/composite2d.py`).

Rule for new Originals: a premise must pass the bible's quality bar —
explainable in one sentence, recognizable cultural behavior, clear visual
scene, strong caption turn, 5+ variations.
