# Flowing light: optical architecture (volume, not dots)

Saved 2026-10-09. Control where light appears AND how it moves —
dimming alone never makes flow. Chosen combo: addressable LEDs +
custom light-guide + mineral shell (options 1+3). OLED reserved.

## Four options (verdicts)

Diffused addressables (12–24 on curved path, overlapping gradients):
prototype pick — breath + direction, cheap. Fails without real
diffusion (discrete dots). Light pipes/fibres: gorgeous organic
trajectories, but one-end injection can't address along length.
Layered optics: floating 3D field feel; crosstalk + thickness
limits. OLED-under-shell: true vortices/particles; power-hungry,
flat, screen-like.

## Built target (29mm Stone)

16–24 tiny RGB on TWO curved tracks (never one straight strip) →
frosted optical insert → 4–8mm LED-to-diffuser separation (Adafruit:
material + distance decide pixels-vs-glow) → dark mineral outer.
30–60fps local animation on the BLE MCU (phone sends trajectory
params + scheduled events; stutter-proof). Very low brightness,
calibrated ceiling. Low-brightness gradients want 16-bit PWM
(TLC59711-class) over plain addressables. Preferred shell: B +
a little C — two S-shaped paths at different depths, mergeable
into one field. Same engine later fits deity models, astro
instruments, Glimlings.

## Command schema (DeityBody extension)

breath{source,phase,expansion,confidence} + light{mode,path,
position,width,intensity,color} + haptic{mode}. `measured` valid
only with a real respiration source. Per-LED law: moving Gaussian
I=A·exp(−(s−p)²/2σ²) on path positions, smooth interp, perceptual
correction, local frame gen. One law, many effects: swell, travel,
opposing currents, gather-to-centre. Implemented:
backend/lightfield.py (positions, width, intensity, path; gamma +
smoothing; breath→field and stillness mappings).

## Experience beats

Guide: "watch this light rise as you inhale" (region travels end
to end) → "close your eyes" (light fades, haptics stay) → user
reports weak locus → guide pauses/repeats, phone shows the locus.
Device guides imagined trajectory; never claims to measure
attention.

## Honest limits

LED flow is illusion (16 diodes: gradients yes, detail no).
Over-diffusion kills direction — structure must blend neighbours
while keeping regions distinct. 2D paths beat volumetric currents;
true 3D swirl needs layers or display. Brightness is battery:
soft glow practical, full-white never a normal mode. Local control
or stutter. Prototype order: ONE curved LED PCB × three shells
(A diffuse / B channels / C layered); JLCPCB assembles board,
JLC3DP prints optics/carrier/shell; we test assembled optics.
