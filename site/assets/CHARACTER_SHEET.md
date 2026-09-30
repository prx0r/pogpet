# Bartholomew Character Sheet

**Source:** 4 AI-generated character images from R2

---

## Assets

| File | Size | Mode | Use |
|------|------|------|-----|
| `bartholomew-01.png` | 1254x1254 | RGB | Original avatar (brand mark) |
| `bartholomew-02.png` | 1448x1086 | RGBA (45% filled) | Pose A — primary character |
| `bartholomew-03.png` | 1448x1086 | RGBA (34% filled) | Pose B — alternate expression |
| `bartholomew-04.png` | 1448x1086 | RGBA (52% filled) | Pose C — alternate expression |

## State Mapping

| State | Image | Animation |
|-------|-------|-----------|
| IDLE | bartholomew-02.png | Gentle hover (y oscillation) |
| THINKING | bartholomew-03.png | Slow hover + head tilt |
| EXCITED | bartholomew-04.png | Scale bounce + wing burst |
| FLYING | bartholomew-02.png | Fast movement + wing flutter increase |
| TALKING | bartholomew-04.png | Mouth open/close (audio reactive) |
| CELEBRATE | bartholomew-04.png | Scale bounce + rotation |

## CSS State Classes

```css
.bee--idle { animation: bee-hover 2.5s ease-in-out infinite; }
.bee--thinking { animation: bee-think 3s ease-in-out infinite; }
.bee--excited { animation: bee-excite 0.6s; }
.bee--flying { transition: transform 0.8s cubic-bezier(0.34, 1.56, 0.64, 1); }
.bee--talking { animation: bee-talk 0.2s step-end infinite; }
.bee--celebrating { animation: bee-celebrate 0.6s; }
```

## How to Improve Later

1. **Extract layers** from bartholomew-02.png (body, eyes, mouth, wings, antennae)
2. **Create Motion.js skeleton** for bone-based animation
3. **Add Rive state machine** for complex character animation
4. **Inworld voice** for conversational interaction
5. **three.ws 3D** for AR and marketing

But for V1: **image swapping + CSS animations + page movement = already magical.**
