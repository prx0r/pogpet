# Pro camera hooks (founder research, verbatim 2026-10-10)

> Pro footage is mostly camera grammar: a moving lens, shallow depth of
> field with a focus pull, motion blur, slight handheld shake, speed
> ramps. Build those once as reusable camera rigs — every product gets a
> hook for free. Flat images (cards, Etsy stills) get the same push-ins
> via depth map. Implemented: `motion/` library (hooks + recipe validator,
> Blender execution next), `backend/creative/motion.py`.

## The gold approach

A hook library: 8–10 camera rigs saved once in the scene kit. Each takes
any pack mesh, auto-frames it from its bounding box, renders a 1.5–2.5 s
opener. Pick the hook per listing, add the shared spin/detail/end card.
Cost $0, works for every SKU forever.

What makes it look pro (all native Blender):

- Depth of field + focus pull: f/1.4–2.8, focus distance animated from
  background to product. Instantly cinematic.
- Motion blur: on for every move. The difference between "render" and
  "footage".
- Handheld shake: Noise modifier on camera rotation F-curves, ~0.3 deg.
  Feels shot, not computed.
- Speed ramps: ease curves that snap fast, then slow to hold on product.
- Bokeh lights: tiny emissive spheres out of focus behind (fairy lights
  for Christmas).
- Real lens choice: 85–135 mm product, 24 mm dramatic low angle.

## Hook rigs to build

- Rack focus reveal: blurred foreground prop (gift ribbon) → focus snaps
  to product.
- Macro slide: 100 mm macro glides across personalised name, pulls back
  to whole object.
- Crane down: start on bokeh background, tilt + drop onto product.
- Push-in + dolly zoom: vertigo effect on the face; figures and pets.
- Drop-in: product falls in, squash, dust puff, micro-shake on impact.
- Orbit whip: fast 90° orbit with motion blur settling to hero angle.
  Good for match-cutting to next shot.
- Lid lift: gift box lid rises, light spills, product revealed.
- Photo → product match cut: customer photo fills frame, cut on same
  silhouette to rendered mesh. Best personalisation hook.

## Flat images (cards, wrapping paper, Etsy stills)

- Depth map from image (Depth Anything V2 Small, Apache-2.0) → displace a
  plane in Blender, or three.js parallax shader.
- Same rigs apply: push-in, ~5° slow orbit, rack focus. A card becomes a
  3D-photo shot.
- Even cheaper: card art on a real card mesh (folded 7×5, slight paper
  bump), opened on camera.

## Agent contract

```text
motion recipe = {hook: "rack_focus", body: ["spin360", "detail"],
                 end: "logo", mood: "xmas"}
```

Auto-frame from bbox; preview at 240 px, final at 1080; cache by
(mesh_hash, recipe_hash). Gate: first 1 s holds the hook, product on
screen within 0.5 s. Generate motion as part of the product pack
(pack `listing/` gains motion renders; schema change proposed, not made).
