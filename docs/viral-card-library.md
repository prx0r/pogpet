# Viral card template library

The canonical creative unit is **not a finished card**. It is a reusable joke grammar:

`occasion × audience × premise × render style × recipient facts/assets → immutable scene revision`

`templates/catalog.json` is the browse/discovery source shared by the storefront and agents.
Hand-authored `templates/<style>/<id>/manifest.json` files remain authoritative when a
template graduates to a bespoke layout; the catalog only supplies presentation metadata
and synthesizes a generic executable manifest for ideas that do not yet have one.

Current style families:

- `xmasaisketch`
- `original` (house Originals you can just buy — no photo needed; premise bible: `docs/original-premise-bible.md`)
- `comicstory`
- `studioroast`
- `sportspresser`
- `newsparody`
- `cinechaos`
- `screenshottalk`

The Cards tab renders the library as horizontally swipeable style rails. ChatGPT/Muse
see the same records through `/api/creative/catalog` / `figg_creative_catalog`.

Generated scene imagery should never own final typography. Captions, lower thirds,
bleed, print geometry and video overlays remain deterministic OddHobb layers.
