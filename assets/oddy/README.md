# assets/oddy — CANONICAL Oddy emotion pack. Source of truth for the mascot.

Twelve states, tiny-tuft rails, open-top loops that meet (never overlap) at
the center knot — the face of the canonical mark. Shared 512 viewBox.

States: neutral, happy, listening, thinking, speaking-small, speaking-wide,
confused, idea, wink, sleepy, surprised, delighted.

| Consumer | How it reads this folder |
|---|---|
| `site/img/oddy/` | Working copies served to the page (rects stripped for transparency). |
| Inline `<symbol>` block in `site/index.html` | The live component. Regenerate from here, never hand-edit. |
| `site/js/oddy.js` | State machine. Schema matches these 12 filenames exactly. |
| Future Rive build | Same 12 states become inputs; filenames are the contract. |
| Future 3D Oddy | Face reference. Meshy concepts must match these eyes. |

Rules:

1. New emotion = new file here first, then wire. No orphan states in code.
2. Geometry edits touch all 12 (shared body group) — script it, like the
   knot fix. Verify by rendering neutral + happy minimum.
3. `data/logo1/oddy/` holds superseded packs (v2, manual fix). History only.
