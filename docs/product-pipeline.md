# Product pipeline: any person, pet or character -> every Prodigi product

One code path for everyone. Nothing in the backend knows who "Chris" or "Jenny" is:
a subject is registered from photos, the photo selector finds them, and each product
is composed from **data** (`backend/product_recipes.json`). Outputs (print files and
mockups) are side effects of the calls below.

```
photos ──> subject_intake.add_subject ──> photo_select.select_photos ──> product_art.make_product
           (upload route, YuNet faces,      (likeness, sharpness,          (recipe -> print file at exact
            one confirmation tag)            dedupe, variety, crops)         print px + scene mockup)
```

| layer | file |
|---|---|
| intake (person / pet / character) | `backend/subject_intake.py` |
| selection | `backend/photo_select.py` (whole-image tags for faceless pets/characters: `subject_region`) |
| recipes (data) | `backend/product_recipes.json` |
| composition | `backend/product_art.py` (`make_product`, `make_all`, `make_and_store`) |
| background removal | `backend/cutout.py` (premesh / rembg / flat / grabcut behind one interface, `quality()` gate) |
| listing mockups | `backend/mockup_slots.py` `render_scene` (scene kits in `assets/mockup_scenes/`) |

## CLI

Uses the backend's own config (`FIGG_DATA`, `RCLONE`, `R2_REMOTE`), exactly like the server.

```bash
# register anyone from a folder, files, URLs or existing photo ids
python3 scripts/make_products.py add-subject --name Jenny --photos ~/pics/jenny/ [--kind person|pet|character] \
        [--relationship daughter] [--interests "dancing,telly"] [--owner local_owner]
#   -> {"subject": {"id": "sub_..."}, "photos": [...], "tags": [...]}
#   add more photos later:  add-subject --subject sub_... --name Jenny --photos more.jpg

# every product (or a list), same make_all the REST/MCP use
python3 scripts/make_products.py run --subject sub_... --products all|mug,tote,wrapping_paper \
        [--age 70] [--recipient Mum] [--style classic|bold|playful|botanical|sporty|kids] [--out DIR] [--store]
#   --out   writes <product>_print.jpg + <product>_preview.jpg there
#   --store also uploads + records them and prints the public proof URLs (what REST returns)

python3 scripts/make_products.py subjects     # list who is registered
```

## REST

| method | path | body | returns |
|---|---|---|---|
| POST | `/api/subjects/intake` | JSON `{name, kind, relationship?, interests?, photo_urls?, photo_ids?, subject_id?}` or multipart with `photos` files + the same fields | `{subject:{id,...}, photos, tags, errors}` |
| POST | `/api/products/make` | `{subject_id, product_id: <id>|"all", products?: [...], age?, recipient?, style?, photo_ids?, fresh?}` | `{products:[{product_id, print_url, preview_url, print_px, aspect_source, picks[{photo_id, hero, reason}], recipe_version, note}], failed:{}}` |
| GET | `/api/products?owner=&subject_id=[&age=]` | | the product grid for that person (`image` = mockup, `print_image` = print file) |
| GET | `/api/products/proof/<make_id>/print.jpg` · `/preview.jpg` | | public, unguessable capability URLs |

Owner auth is the usual: the owner's `X-API-Key`, or an owner signature on the service token.
Makes are cached per (recipe version, inputs, photo library fingerprint): asking again is free.
**Fulfilment only ever uses `print_url`.** `preview_url` is the listing mockup.

## MCP

| tool | what |
|---|---|
| `oddhobb_subject_add(name, kind, photo_urls?, photo_ids?, relationship?, subject_id?)` | intake |
| `oddhobb_product_make(subject_id or person, product="all"|<id>, age?, recipient?, style?)` | products |
| `oddhobb_make(person, product="all"|<id>, request="... he's turning 70")` | the public-tier entry; without `product` it still makes the photo-grid birthday card |

## Kinds

* **person**: the anchor is the largest face in the first single-face photo (else the largest
  face anywhere). The selector finds them in every other photo by SFace likeness; group photos
  are fine, strangers in the background are ignored.
* **pet / character**: a detected face is tagged the same way; a photo with no detectable face
  is tagged as a whole image and the selector takes the subject region from the image itself
  (foreground against the border colour). One or a few images are enough. Character renders may
  be as small as 300 px on the short side (photos need 480); the reasons say what DPI each
  product prints at. Cutouts use the `flat` matte (characters) or GrabCut (pets) instead of the
  human segmenter.

## Recipes (`backend/product_recipes.json`)

```json
"poster": {
  "kind": "grid",                       // card | grid | sticker_round | mug_band | wrap_pattern
  "print_px": [3508, 4961],             // fallback print size
  "aspect_source": "assumed",           // verified | assumed  (live when prodigi.print_area(sku) answers)
  "aspect_note": "A3 portrait 297x420mm at 300dpi",
  "photos": {"ideal": 6, "min": 1},     // steps down to the biggest layout the photos fill, and says so
  "layouts_by_count": {"6": "g6", "4": "g4", "3": "g3", "1": "g1"},   // ids in "layouts" (unit-grid spans)
  "header": {"pos": "top", "frac": 0.22},     // photo_grid lettering plate + typeset age/name
  "margin": 0.06, "gutter": 0.014, "style": "auto"
}
```

A new product is a new entry (and a scene kit), not new code. `validate_recipes()` runs on load.

## Wrapping paper

Background-removed head-and-shoulders cutouts from up to 6 **different** photos, white
sticker outline + soft shadow, ±15° rotation, every face the same size, ~9 heads across
the 50x70 cm sheet. The repeat is an exact half-drop lattice (tile `Tw x Th`, vectors
`(Tw, Th/2)` and `(0, Th)`) rendered by wraparound, so the sheet is an excerpt of an
endless pattern and nothing is clipped at tile edges. Touching heads never share a photo
(backtracking colouring across the wraparound). Confetti (stars, strips, triangles) is
rejection-sampled into the gaps; a small "Happy 70th" motif appears when an age is given.
Cutouts whose face the matte lost, or whose head reads as a dark silhouette
(`cutout.quality`), are dropped and listed in `cutouts_dropped`.

## Tests

`tests/test_product_art.py` (with `test_mockup_slots`, `test_photo_grid`, `test_public_six`, `test_wrap`).
Real-photo harness: `product_pipeline/harness/` in the project workspace.
