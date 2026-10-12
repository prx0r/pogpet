# Pogtown Comedy Club player (Videos tab)

The top of `/videos` plays a comedy set live in the browser with Rive: the shared club (`club.riv`, artboards
`ClubBack` and `ClubFront`) and one character `.riv` (artboard `Character`, state machine `Acting`) are drawn on one
9:16 canvas under one camera, driven by the director's keyframes. Captions and the name tag are DOM overlays.
The rendered MP4 of each set is the fallback (no WebAssembly, or any Rive load error) and also leads the swipe feed
below the player; user clips from `GET /api/videos/feed` follow unchanged.

| piece | path |
|---|---|
| player (ES module, lazy-loaded on the first visit to Videos) | `site/js/club-player.js` |
| markup + CSS + feed hook (`loadClub`, `clubFeedItems`) | `site/index.html`, section `panel-videos` |
| Rive runtime (vendored, MIT) | `site/vendor/rive-canvas-advanced-2.44.2/` (`canvas_advanced.mjs`, `rive.wasm`) |
| set bundles | `site/assets/club/manifest.json`, `club.riv`, `<id>/{<id>.riv,set.json,set.m4a,set.mp4,poster.jpg}` |
| bundler | `scripts/club_bundle.py` |

`?club=mp4` on the URL forces the MP4 fallback (testing).

## Add a set

Sets are made in the rivelab character system (skin pack -> `.riv`, then `director/make_set.py`,
`director/direct.py -o plans/<id>.plan.json`, `director/render.py plans/<id>.plan.json out/<id>_club_15s.mp4`). Then:

```bash
python3 scripts/club_bundle.py <rivelab>/plans/<id>.plan.json --mp4 <rivelab>/out/<id>_club_15s.mp4
```

This copies the character and club `.riv`, bakes the plan to `set.json` (view-model tracks simplified within 0.004,
events, captions, tag), writes `set.m4a` with the plan's `audio_offset` already applied (so the player clock is
`audio.currentTime`), re-encodes the MP4 to 720x1280 (`--mp4-height 0` keeps it as is), grabs a poster, and upserts
the set into `manifest.json`. The picker and the feed read the manifest, so nothing else changes. Skins marked
`"private": true` in their `skin.json` are refused; never bundle a private skin. Remove a set by deleting its folder
and its manifest entry.

## Deploy

Static files only; no backend change. Pull and serve `site/` as before; the server must send `rive.wasm` as
`application/wasm` and `.mjs` as JavaScript (it already does for the other vendored wasm/mjs). About 11 MB of new
static assets (runtime 2.1 MB, two characters 3.8 MB, two MP4s 4.1 MB). Bump `?v=club-N` on the `club-player.js`
import in `index.html` when the player changes.

## Limits

Head turns are cuts between drawn views; captions use estimated word times (about 100-200 ms late); rendering is
Canvas2D on the main thread (smooth on phones, about 10 fps in a 2-CPU headless test box).
