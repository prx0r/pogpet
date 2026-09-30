# Bartholomew Character Breakdown

**Source:** bartholomew.png (MythicBee avatar, 1.5MB)

---

## Character Sheet

From the canonical artwork, separate into movable layers:

### Static (don't animate)
- body/thorax
- abdomen
- cape-upper
- cape-lower

### Animated
- **head** — tilt, nod, turn toward mouse/target
- **left eye** — blink, follow cursor
- **right eye** — blink, follow cursor
- **mouth** — open/close for talking (audio-reactive)
- **antenna L** — bounce, twitch
- **antenna R** — bounce, twitch
- **front wing L** — flutter cycle
- **front wing R** — flutter cycle
- **rear wing L** — flutter cycle (offset phase)
- **rear wing R** — flutter cycle (offset phase)
- **front arm** — point, wave

### How to Separate

1. Open bartholomew.png in image editor (Photoshop/Figma/Photopea)
2. Use selection tools to isolate each component
3. Export each as transparent WebP/PNG
4. Name files: `body.webp`, `eye-l.webp`, `eye-r.webp`, `mouth.webp`, `antenna-l.webp`, `antenna-r.webp`, `wing-fl.webp`, `wing-fr.webp`, `wing-bl.webp`, `wing-br.webp`, `arm.webp`, `cape-upper.webp`, `cape-lower.webp`
5. Place in `assets/layers/`

### Motion.js Animation Plan

```javascript
// States
IDLE     → gentle hover (y oscillation)
FLYING   → fast movement + wing flutter increase
LANDING  → decelerate + wing slow
LISTENING → eyes toward user + wing slow
TALKING  → mouth open/close (audio amplitude) + subtle head bob
THINKING → slow hover + occasional head tilt
REACTING → expression change + bounce
CELEBRATE → scale bounce + wing burst + sparkles
```

### CSS States

```css
.bee-character { position: fixed; z-index: 1000; }
.bee--idle { animation: hover 2s ease-in-out infinite; }
.bee--flying { transition: transform 0.8s ease-in-out; }
.bee--landed { animation: gentle-bounce 3s ease-in-out infinite; }
.bee--listening .bee__eyes { animation: look-toward 0.3s; }
.bee--talking .bee__mouth { animation: talk 0.2s step-end infinite; }
.bee--celebrating { animation: celebrate 0.6s; }
```

---

## Next Steps

1. **Extract layers** from bartholomew.png (manual or AI-assisted)
2. **Wire bee-controller.js** into index.html
3. **Add CSS states** for each animation
4. **Test page flight** (bee moves around page)
5. **Add Inworld voice** (WebRTC + function calls)
6. **Define GiftBrief** + function call schema
