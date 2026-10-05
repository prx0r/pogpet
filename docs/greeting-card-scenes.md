# Greeting cards: saved scenes and matching MP4s

Implemented locally against `24ea88f6360a66aa8e940051e080a3fe7a15be82`.
No push, deployment, paid generation, or external order was performed.

## Running the implementation

This v2 patch is cumulative and includes the original card implementation.
Apply it to a clean checkout at the base commit above, not on top of the v1 patch
(`git apply --check oddhobb-scene-links-v2.patch`, then `git apply`). Keep the
existing Flask/Pillow/R2 environment. MP4 rendering additionally requires
`ffmpeg` with libx264 on PATH; if absent, the UI disables motion. Background
removal requires the existing `premesh` package and Cloudflare configuration.
The backend entry point initializes the additive card tables automatically:
`python3 -m backend.server`. Start the existing bridge normally for browser
access. Do not run multiple backend processes with this initial job worker.

## Customer journey

Studio now has a photo library independent of meshes. Upload several JPEG/PNG
photos, select up to five, and choose **Make a greeting card**. Photos are
persisted through the existing intake/R2 registry. The default daily photo
allowance is 30; the separate Meshy credit allowance is unchanged. Deployments
that explicitly configure `DAILY_UPLOAD_LIMIT=3` must change that override.

The Cards tab offers seven scene templates: portrait, family collage, breaking
news, game winner, lifetime achievement, Christmas cast, typography. Choose
the scene, crop photos, adjust image focus, edit headline/recipient/sender and
inside message, then save. Edits autosave after a pause. **View linked video**
opens that saved scene in Videos; **Open linked card** returns to its editor.
Videos can render a matching MP4 without changing its card revision. **Bring this card to
life** renders a six-second MP4 from the same saved scene. **Download print
PDF** produces a generic 300dpi document with 3mm bleed.

For group pictures, explicitly crop around Dad before **Remove background**.
That reuses `premesh` foreground segmentation, caches the cutout and retains
the original. Generative upscaling is disabled. Segmentation is an explicit
customer action; it uses the deployment's Cloudflare transformation service
and its normal quota. Offline verification mocks this service. It is not a
face recognition system and cannot separate heavily overlapping people.

Saving a new card retains the selected photos/crops, so they can be reused
across scenes. Existing designs reload from the server, with optimistic
revision checks to avoid overwriting changes made in another tab.

## What is actually animated

- All scenes reveal their photograph(s) and headline.
- News adds a moving ticker.
- Champion/awards add deterministic confetti.
- Christmas adds deterministic snowfall.
- The final MP4 frame is the saved card front at video resolution.

**There is no rigged golf swing, face swap, neural video generation, speech,
lip sync, automatic person identity grouping, or customer mesh animation in
this version.** The game-winner clip is a champion reveal. All artwork is
composed from customer images and original vector/layout elements. No movie
footage or third-party character art is bundled.

## Files and seams

| File | Responsibility |
| --- | --- |
| `backend/card_scenes.py` | Canonical formats/templates; proportional layouts; front/inside/PDF/MP4 |
| `backend/cards.py` | Owner auth, source validation, revisions, jobs, cutouts, reservations |
| `site/js/cards-studio.js` | Studio library, batch upload/retry, scene editor, crop controls, save/reload |
| `site/css/cards-studio.css` | Responsive editor styling |
| `backend/server.py` | Blueprint registration and startup schema initialization |
| `backend/mcp_server.py` | Same card workflow exposed to agents |
| `tests/test_cards.py` | Offline customer journey with real SQLite/PIL/ffmpeg and fake R2 |

## HTTP API

All routes use the existing service gate plus the exact owner's signature or
API key. Pass owner on every request, including images and downloads. Customer
artwork is served through private routes, never `/img/` marketing assets.

| Method/path | Purpose |
| --- | --- |
| GET `/api/cards/templates` | Scene and format registry; motion availability |
| GET `/api/cards/photos` | Photos, without requiring meshes |
| GET `/api/cards/photos/<id>/image` | Owner-checked source image |
| POST `/api/cards/cutouts` | `{photo_id,crop:[x,y,w,h]}` → cutout ID |
| GET `/api/cards/cutouts/<id>/image` | Owner-checked cutout |
| GET/POST `/api/cards/designs` | List/save; updates need `id,expected_revision,spec` |
| GET `/api/cards/designs/<id>` | Reload latest saved revision |
| GET `/api/cards/<id>/scene?revision=<n>` | Shared, owner-gated scene manifest with output status/capabilities |
| POST `/api/cards/<id>/render` | `{revision,kind:preview|export|motion}` → job |
| GET `/api/cards/jobs/<id>` | queued/running/ready/failed, with download URL |
| GET `/api/cards/<id>/r<revision>/<kind>` | Ready front/inside/PDF/MP4 |
| POST `/api/cards/<id>/order` | `{revision,qty,idempotency_key}` → real card reservation |

Example `spec`:

```json
{
  "template": "breaking_news",
  "format": "5x7",
  "headline": "Local dad officially declared a legend.",
  "recipient": "Dad — 60 today",
  "sender": "Love from Mum and the kids",
  "inside_message": "Happy birthday!",
  "photos": [{"photo_id": "<owned photo>", "crop": [0,0,1,1],
              "focus": [0.5,0.5], "cutout": ""}]
}
```

## Integrity and job behavior

The saved revision is immutable. Orders keep the exact design revision, full
specification and export key; no data is packed into an ornament note. Prices
come from the server format registry and are estimates in GBP. Duplicate
reservation keys reuse the same order; conflicting reuse returns 409.

Two render workers and a six-job admission limit bound work. Repeated requests
for the same ready/inflight revision reuse its job. Failed jobs can retry;
queued/running jobs interrupted by restart become retryable failures. Artwork
is persisted to R2 before a job becomes ready. Partial output is never served.
Local derived cache uses full-key hashes. Files can be recovered from R2.

The worker is a per-process thread pool for this single-process Flask
deployment. Before moving to multiple WSGI processes, use a shared job worker
and lease/claim protocol: startup recovery is not a multi-process scheduler.
No automatic retention policy is introduced; monitor derived-artwork storage.
Anonymous-to-account claiming transfers card designs, jobs, cutouts and
reservations with existing photos/videos. Artwork namespaces remain stable;
source photos are copied during claiming when cards reference them. Card
downloads check the current database owner, and the generic artifact gateway
rejects card keys. Finish any active card render before signing up, then retry.

## Printing and checkout boundaries

A6 exports front/back pages. Folded 5×7/A5 export an outside spread (back at
left, front at right) and inside spread (blank left, message right). The PDF
has 3mm exterior bleed and 300dpi raster art. Low effective photo resolution
is reported when saving. It is **not an attached Prodigi SKU or guaranteed
supplier-ready job**: verify supplier panel/bleed/colour specifications first.

Reservations go into `card_orders`, status `pending_checkout`. They do not
charge, create Shopify drafts, or dispatch to a printer. The UI says so.
Connect real card supplier SKUs and shipping/payment next; do not restore the
old `line=ornament` fallback. Keep the artwork reference and revision as
structured supplier metadata, and implement separate checkout idempotency.

## Extending to the golf animation / OddHobb meshes

Keep a scene's text/subject slots stable. Add a renderer capability for a
prepared character scene, rather than replace the saved design model.

1. Author a standard body rig, consistent scale, head socket and prop sockets.
2. Import one clean putt/celebration performance; clean feet, hand/club contact,
   club/ball contact and trajectory. This is reusable template authoring work.
3. Bind a customer's existing mesh/portrait to that rig after validating their
   ownership. Keep source photo and character IDs explicit and distinct.
4. Render the personalised poster frame and MP4 with the same scene parameters.
5. Keep motion jobs asynchronous and reuse static background layers where
   possible. Never assume a random Meshy mesh is rig-compatible.
6. Version the scene/rig/animation assets and include them in cache identities.
   A changed renderer needs a new template version, never overwrite approved
   artwork. Old jobs/orders continue using their pinned exports.

The generative alternative can later implement a different renderer with the
same saved-scene interface. It needs explicit cost approval, provenance and
identity/prop QC; it is not necessary for the current deterministic scenes.

## Verification

```bash
python3 -m unittest discover -s tests -p test_cards.py -v
python3 -m unittest discover -s tests -p test_motion_contract.py -v
node --check site/js/cards-studio.js
python3 -m compileall -q backend
git diff --check
```

The existing `scripts/test_site.py` targets deployed public services and needs
the live bridge token. It was not run against these unpushed changes.
The wider offline suite includes two factory tests requiring missing
gitignored STL masters; those are unrelated to card code.

Browser verification used local fake R2 with no external calls: five uploads,
scene editing, PDF reservation, real MP4, saved design reload and a 390px mobile
viewport. There were no page errors or horizontal document overflow. Cutout
provider success/failure was verified offline with a mock, not live credentials.

## Shared scenes and rehearsal follow-up

The owner-gated `oddhobb.scene.v1` manifest joins card, video and poster output
references at one immutable revision. It explicitly reports
`renderer=photo_composition`, `character=null`, `performance=null` and `ar=false`.
It does not imply a generated photo card is already a rigged character.
`figg_card_scene` exposes the same manifest through MCP.

The Videos tab contains a saved scene library alongside the existing mesh
video feed/live stage. This is a working two-way card/video navigation flow;
it reuses the renderer/job cache, source assets and editing permissions.

`/rehearse.html` is a separate local authoring tool: load a self-contained
animated/skinned GLB, select a clip, play/pause, scrub and download a PNG poster.
It offers WebXR AR only when the browser/device supports it. No uploaded customer
character is bound automatically; no rehearsal files are persisted/uploaded.
The native Quick Look/iPhone export path is not implemented. The Google
model-viewer 4.3.1 distribution is vendored unchanged with its license and
embedded dependency notices, avoiding a new CDN requirement for basic playback.
Official reference: https://modelviewer.dev/examples/augmentedreality/

The GLB authoring inspector and next integration steps are documented in
[motion-authoring.md](motion-authoring.md). Playback, clip duration, scrubbing
to 1.20 seconds and PNG poster export were verified with a synthetic skinned
GLB in Chromium. Desktop correctly reported AR unavailable; a real phone AR
session has not been tested. Cards → render in Videos → reopen Cards was also
verified without page errors.
