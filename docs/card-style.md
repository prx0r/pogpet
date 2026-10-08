# Card style guide — for agents and humans making cards

The renderer owns all geometry. This doc owns taste. Read before proposing
any card design change.

## Type system (`assets/fonts/`, all OFL, commercial-print-safe)

| Role | Font | Used for | Never for |
|---|---|---|---|
| display | Fraunces SemiBold | headlines, titles | body, small print |
| hand | Caveat SemiBold | recipient names, signatures | body, headlines |
| sans | Inter Regular/Bold | body, captions, fine print | headlines |

Max 3 fonts per card (we use exactly these 3). DejaVu is the emergency
fallback in code, never a design choice — if you see it in a render,
a font file is missing, not a style decision.

## Canonical back

Every card back is renderer-owned: `oddhobb.` wordmark (display),
tagline, oddhobb.com, quiet margins. No AI input, no exceptions. See
`back()` in `backend/card_scenes.py`.

## Rules that prevent ugly cards

1. One headline per front, ≤54 chars, display face. If it doesn't fit,
   shorten the words — never shrink below legibility.
2. Names always in hand face. A name in sans looks like a shipping label.
3. Body text left-aligned, Inter, generous leading. Centered paragraphs
   longer than two lines look amateur.
4. Contrast: ink on paper tones only. No grey-on-grey, no white-on-yellow.
5. Photos get white space around them. Edge-to-edge photo + edge-to-edge
   text = flea market.
6. Inside-left stays blank or holds ONE secondary joke. Never two.
7. Every grammar in `backend/card_grammars.py` is a hard constraint, not a
   suggestion. Four panels means four.
