# Pulse: OddHobb's loader engine

One engine for every loading moment. It plays a sprite-sheet animation on a heartbeat: each run plays at a slightly different speed, and the rest between runs breathes. It's regular overall, never mechanical.

## Use

```html
<link rel="preload" as="image" href="/assets/pulse/emerge.webp">
<script src="/js/pulse-loader.js" defer></script>
<div data-pulse="emerge" style="--pulse-size:72px" aria-label="Loading"></div>
```

JS: `const p = PulseLoader.mount(el, "emerge", {tempo: 1.2})` → `p.stop() / p.start() / p.setTempo(x) / p.destroy()`.
Auto-mounted elements expose their instance as `el._pulse`.

## The rhythm (heart-rate variability, not random)

```
interval_n = mean × (1 + rsa_n + drift_n + jitter_n)      clamped
  rsa_n    0.07 × sin(2π n / 4.3 + φ)   breathing cycle across ~4 beats
  drift_n  0.72 × drift_{n-1} + 0.05·N(0,1)   correlated wander between beats
  jitter_n 0.025·N(0,1)
speed  = clamp(1 − 0.9·dev, 0.84, 1.18)   a quicker beat plays quicker
rest   = clamp(0.75 s × (1 + 1.6·dev), 0.35 s, 1.35 s)
```
At tempo 1, emerge runs 2.46-3.45 s per beat (mean 2.91), with 0.35-1.22 s rests (mean 0.74), from 5,000 simulated beats.
During the rest it holds frame 0, the flat, near-invisible mark, so each beat reads as the mark emerging, turning and sinking back.

## Add a loader

1. Render frames (RGBA), then build a sheet: `python3 tools/pulse/build_sprite.py <px> site/assets/pulse/<name>.webp <step> <quality>`
2. `PulseLoader.define("<name>", {sprite, frames, cols, px, still, beat:{...}})`, or add it to `PRESETS` in `site/js/pulse-loader.js`.

## Rules

- Small: 56-80 CSS px. The sheet is 144 px per frame, so it stays crisp at 72 px @2x.
- No caption under the loader.
- Reduced motion shows one still frame (`still`). Background tabs pause it, and the canvas is DPR-aware.
- `emerge.webp`: 66 frames (every 2nd of the 132-frame Blender render), transparent, 379 KB.
