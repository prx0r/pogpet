# fal.ai — endpoint map (imported 2026-10-10, not rewritten)

Key: `FAL_KEY` in `.env` (0600, gitignored). Server-side only — never in
the browser (fal's own guidance; matches our bridge-token pattern).
Sources: `https://fal.ai/models/<endpoint>/llms.txt` + API pages.
Dispatcher: `backend/restore.py` DEFECTS. Spend gate: ask-first, ledger
`data/restore_ledger.jsonl`.

## Restoration (photo rescue)

| Defect | Endpoint | Key params | Notes |
|---|---|---|---|
| blur (motion/focus) | `fal-ai/nafnet/deblur` | `image_url`, `seed?` | output PNG info (url/width/height) |
| noise (ISO grain) | `fal-ai/nafnet/denoise` | `image_url` | same family as deblur |
| haze/fog | `fal-ai/mix-dehaze-net` | `image_url` | from community recipe |
| face (distorted/low-res) | `fal-ai/codeformer` | `fidelity` 0–1 (0 quality / 1 identity; 0.5–0.7 balanced), `upscale_factor` 2, `face_upscale`, `only_center_face`, `aligned` | ~$0.0021/MP ≈ 476 512px restores per $1 |
| low resolution | `fal-ai/esrgan` | `scale`, `model` (RealESRGAN_x4plus default; v3/anime variants), `face` bool, `tile` | general upscale |
| flat look | `bria/aesthetics/upscaler` | fixed 4MP | lighting/colour/sharpness boost |

Chain order: denoise → deblur → face-fix → upscale (dispatcher CHAIN).
Face rule: don't over-restore — low fidelity melts identity into generic
AI face. Always keep before/after; originals immutable.

## Matting (stickers, cutouts)

| Use | Endpoint | Key params | Notes |
|---|---|---|---|
| subject cutout | `fal-ai/birefnet` | `model`: General Use (Light) default / (Heavy) accurate / **Portrait** for faces; `operating_resolution` 1024/2048; `refine_foreground`; `output_mask` | PNG + optional mask; metered per compute-sec (~$0) |

Stickers want Portrait-or-Light matte of the face/body crop; wrap uses the
full photo (no matte). Matte output feeds `mockup.render("sticker")`
sources and future sticker-SKU order assets.

## Calling

Direct POST `https://fal.run/<endpoint>` with `Authorization: Key $FAL_KEY`
(works for fast models); queue + webhook for slow ones. Inputs accept
public URLs or base64 data URIs (convenient, slower for large files); fal
storage upload when neither fits. Our R2 presigned/public URLs
(`storage.public_url`, `/img/`) serve as `image_url`.
