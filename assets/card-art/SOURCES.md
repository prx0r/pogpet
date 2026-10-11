# Card art library (all CC0 public domain — free for commercial print)

Downloaded as transparent PNGs (800px) from Clipart.Free (Openclipart
sources). No signup, no watermark, no attribution required. Keep this file
with the art: every file here must be CC0/public-domain.

| File | What | Artist | Source page | License |
|---|---|---|---|---|
| `birthday-cake-3-304095-800.png` | birthday cake with candles | Firkin | https://clipart.free/clipart/birthday-cake-3-304095/ | CC0 |
| `birthday-cake-296924-800.png` | birthday cake (alt) | via Openclipart | https://clipart.free/clipart/birthday-cake-296924/ | CC0 |
| `colored-balloons-191040-800.png` | bunch of coloured balloons | via Openclipart | https://clipart.free/clipart/colored-balloons-191040/ | CC0 |
| `balloon-border-3024-800.png` | balloon border strip | via Openclipart | https://clipart.free/clipart/balloon-border-3024/ | CC0 |
| `b-day-card-by-kaddie-291343-800.png` | full b-day card scene (reference) | kaddie | https://clipart.free/clipart/b-day-card-by-kaddie-291343/ | CC0 |
| `frame-mono-colored-34-14201-800.png` | ornamental frame 3:4 | qubodup | https://clipart.free/clipart/frame-mono-colored-34-14201/ | CC0 |
| `pink-bow-170156-800.png` | pink bow accent | via Openclipart | https://clipart.free/clipart/pink-bow-170156/ | CC0 |

Rule (AGENTS.md money rules apply to art too): only files listed here may be
used in renders. New art = new row first.

## Generated backdrops (OddHobb-owned, Cloudflare flux-1-schnell, Oct 2026)

One paid generation per template, reused for every card forever. Text-free
by prompt contract; renderer composites photo slots + live type on top.

| File | What | Source |
|---|---|---|
| `backdrops/birthday_arch.png` | balloon sky, cream bokeh, empty center | Workers AI, TEMPLATE_BACKDROPS prompt |
| `backdrops/birthday_dots.png` | pastel confetti field, empty cream space | Workers AI, TEMPLATE_BACKDROPS prompt |
| `backdrops/birthday_news.png` | navy broadcast studio glow, empty center | Workers AI, TEMPLATE_BACKDROPS prompt |
| `backdrops/birthday_gold.png` | champagne bokeh, golden spots, empty center | Workers AI, TEMPLATE_BACKDROPS prompt |
| `backdrops/birthday_wall.png` | cream garland top edge, rest empty | Workers AI, TEMPLATE_BACKDROPS prompt |

## Photo-grid "Happy Birthday" lettering plates (OddHobb-owned, Oct 2026)

`photo-grid/hb_<style>.png`: six transparent header plates for the photo-grid
card (backend/photo_grid.py), one per lettering style: classic (gold serif +
copperplate), bold (heavy sans + coral bar), playful (brush script + confetti),
botanical (calligraphy + watercolour sprigs), sporty (varsity block), kids
(bubble letters + balloons). Generated ONCE at build time (Hark generate_image,
2026-10-11) on pure white, un-matted to alpha so they composite exactly over
white paper, trimmed, max 1600px wide. Every plate was checked by eye: each
reads exactly "Happy Birthday". Never regenerated at render time; the age and
the name are typeset from bundled fonts.
