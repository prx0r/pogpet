# Photo labels P0 — categories that fill every product

> Status: SPEC + thin slice live (2026-10-10). Founder direction: uploads
> carry granular labels; templates declare what they need (e.g. funny
> template = 2 group images + 1 face); cards go first, Prodigi gifts inherit.
> Selector: `backend/subject_assets.py:select_for_template`. Template
> declarations: `config.PERSONAL_CARDS[*]["requires"]`.

## Label layers (granular on purpose — later layers add, never rename)

| Layer | Labels | Source now | Source later |
|---|---|---|---|
| L1 shot_type | `face` (1 big face) / `solo` / `couple` / `group` (3+) | face count from `photo_faces` | same |
| L2 subjects | confirmed subject ids; unnamed clusters | `photo_subjects` + `faces.suggest` | auto-roster |
| L3 quality | sharpness, exposure, `print_sizes` (card/poster/wrap/canvas eligibility), `rescued` flag | on-box pass; `restore` chain promotes | Alibaba quality + aesthetics scores |
| L4 mesh_fit | single clear subject, fills frame, unoccluded → 0–1 (the makeability rubric for 3D) | rule-based on L1+L3 | model-judged |
| L5 expression + framing | `happy` `laughing` `silly` `shocked` `neutral` `serious` `sleepy` · `close_up` `head_shoulders` `waist_up` `full_body` | **LIVE** `backend/photo_labels.py`: one vision call per photo (OpenRouter, cached in `photo_labels`); heuristic framing without a key, expression `unknown` (never satisfies an ask) | same |
| L6 occasion | `xmas`, `birthday`, `holiday`… from date clusters + object cues (tree, cake) | EXIF date bursts | Qwen-VL / tags |
| L7 safety | moderation flags, watermark, screenshot-vs-camera | Sightengine / heuristics | same |

Queryable today: L1, L2, L3 (face score/area), **L5 expression + framing**, L6-dates. Reserved in the
`requires` schema but not yet queried: L4 mesh_fit score, L6-objects, L7 (blocks at intake instead).

Cards declare the richer per-role form in `cardgen/templates/*.json` → `wants` (see `cardgen/wants.py`);
`wants.to_requires()` turns it into this `requires` dict for products, so cards and products share one vocabulary.

## Template `requires` spec

```python
"requires": {
    "groups": 2,            # L1 shot_type == group
    "faces": 1,             # L1 shot_type == face (or any photo with 1 big face)
    "solos": 0, "couples": 0,
    "subjects": ["dad"],    # L2 names (optional; unnamed fill otherwise)
    "emotions": ["happy"],  # L5 — live: photo_labels (happy also accepts laughing)
    "framing": ["waist_up", "full_body"],  # L5 framing
    "min_face_score": 0.5,  # L3 quality floor
    "occasion": "xmas",     # L6 (optional)
}
```

Selector semantics (`select_for_template`): fill each slot best-first by
face score then recency; hero = highest score overall; distinct photos per
slot unless the template allows repeats; missing slots return `shortfall`
with reasons (never a silent wrong photo). Card listing tags
(`PERSONAL_CARDS[*]["tags"]`, Etsy titles) flow unchanged into listing
packs — photo labels pick the *assets*, card tags describe the *listing*.

## Funny-template example

`comedy trio` card back: slots = 2× group + 1× face. Selector pulls the two
highest-scored group shots + best face close-up for the owner; if only one
group exists the response says so (`shortfall: groups 1/2`) and the UI
offers upload or a stock fallback — never a mislabelled solo.
