# Photoreal mockup scene kits

One folder per Prodigi product (ids = `config.PRODIGI_PRODUCTS` keys), read by
`backend/mockup_slots.py`; `backend/mockup.py:render()` uses them by default and
falls back to the flat PIL tile when a kit is missing.

- `scene.jpg` render base. Paper/board products (card, postcard, sticker, prints,
  canvas): the photo with the printable face neutralised to grey shading.
  Printed-on-surface products (mug, cushion, tote, notebook, jigsaw, wrapping
  paper): the clean plate (same photo, plain white product), so the art is
  multiplied onto the real fabric/ceramic/paper texture.
- `mask.png` soft alpha of the printable face.
- `kit.json` corners (TL,TR,BR,BL scene px), mode (quad | ellipse | cylinder),
  surface (opaque | ink), print aspect, cylinder params for the mug.

Scenes were generated once (photoreal, printable face = pure #FF00FF; clean
plates as edits of the magenta scene) and keyed by `scripts/build_mockup_kits.py`.
Nothing is generated at render time. Bump `mockup.SCENE_VERSION` when kits change.
