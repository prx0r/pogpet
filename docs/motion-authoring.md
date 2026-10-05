# Recorded motion → reusable character scene

## What works in this patch

- Saved Cards and Videos use `oddhobb.scene.v1`, with immutable revision IDs.
- `scripts/inspect_motion.py` inspects authored GLB skeletons/clips and emits
  a draft `oddhobb.motion.v1` asset manifest with a SHA256, rig signature, clip
  index/name/duration and chosen poster timestamp.
- `site/rehearse.html` loads local animated GLBs, plays/selects/scrubs clips,
  exports the current frame as PNG, and offers WebXR placement if supported.
- No motion-capture provider, paid call, asset publishing, character binding
  or Freaktown deployment is invoked.

## Your recording workflow

1. Record the full action with head/feet/hands visible; keep the camera steady.
   A second angle helps when limbs overlap. Include a neutral lead-in pose.
2. Use the chosen motion-capture pipeline to recover movement. This patch
   does not extract motion from footage. Fingers and face need their own
   capture/manual animation; body capture does not imply lip sync.
3. Retarget to one named, versioned OddHobb rig in Blender. Clean feet and
   timing. Export a self-contained GLB with skin, animation and textures.
4. Author prop motion explicitly. For the winning putt, bind the club to its
   hand/socket and animate the ball/hole interaction and celebration. A
   skeletal recording alone will not know when the ball should leave the club.
5. Inspect and rehearse the GLB. Choose a useful card pose; the final card still
   needs its typography and print composition. For transparent/poster-ready
   production assets, bake them through the scene renderer.
6. Publish the reviewed rig/clip/props as immutable template assets, then bind
   an owned customer's compatible character and render the same scene for
   print/video/AR. This publication/binding stage remains to be built.

Example commands (these only read the local file and print JSON):

```bash
python3 scripts/inspect_motion.py putt.glb
python3 scripts/inspect_motion.py putt.glb \
  --clip 0 --rig-id oddhobb-humanoid-v1 --poster-ms 1800
```

The inspector checks GLB framing, embedded time buffers, finite/increasing
animation timestamps, skin joints, clip duration and poster bounds. Rig
signatures include hierarchy/rest transforms/skin joints and inverse bind
matrices when present. They are deliberately conservative; matching rig names
or bone labels alone proves nothing. An equal signature is not a full glTF
validator or a guarantee of good deformation. Use Blender/runtime visual QC.
A retargeted export can have a different signature even when compatible; an
explicit retarget step and review are still required.

Every emitted manifest has `runtime_ready=false` and incomplete contact/likeness
review flags. It is a draft, not permission to auto-publish. No authoring script
relabels an unrigged Meshy model as humanoid. A rigid figure needs an authored
rig or deliberately limited rigid-body animation first.

## Freaktown integration boundary

Read against Freaktown main at the time of this work:

- `contracts/avatar.v1.schema.json` supplies actual avatar capability fields.
- `contracts/performance.v1.schema.json` supplies a sealed performance contract:
  actor/avatar, audio, delivery, timed words, motion cues and hash.
- `backend/models/motion_assets.py` has semantic motion metadata and rig classes.
  Its seed entries have empty asset storage keys by default; names in that
  catalog are not evidence that playable animation files have been published.
- `packages/stage-runtime/README.md` documents unresolved store/type coupling.
- `StageRenderer.loadAvatar` currently rejects a GLB without VRM metadata;
  `StageRuntime` has a similar VRM loading path. Add and test a capability-based
  GLB path before importing ordinary OddHobb character exports.
- No WebXR AR placement/session implementation was found in that checkout.
  The new rehearsal viewer is a separate entry point, not a completed port of
  the live Freaktown show to AR.

Do not make the photo card renderer impersonate a Freaktown performance.
When character rendering is added, a scene revision should pin
`character_id`, `avatar_asset_hash`, `rig_id`, `motion_asset_hash`, `clip`,
`poster_ms`, prop/socket bindings and the sealed performance reference.
`renderer=character_performance` should become available only after ownership,
capability/rig compatibility and artifact readiness have passed.

Standup can use Freaktown audio/delivery/word timing and prepared gestures;
AR reuses the character scene while replacing the virtual camera/background
with tracked room placement. Full audio-synchronised show playback, native
USDZ/iPhone Quick Look and customer scene AR remain future integrations.
WebXR requires HTTPS and a compatible device/browser. Runtime docs:
https://modelviewer.dev/examples/augmentedreality/

## Verification

Ten card tests + four motion-authoring tests pass offline. A Chromium browser
journey checked card/video cross-navigation, reuse of matching MP4, saved
revision reload, mobile layout, GLB playback, 2-second clip detection,
1.20-second seeking and PNG frame export. Static/nonanimated GLBs were rejected, and the rehearsal UI had no horizontal
overflow at 390px. There were no page errors. The GLB
fixture is a simple synthetic skinned block, not a real captured golf swing;
contact quality and phone AR need testing with the actual authored assets.
