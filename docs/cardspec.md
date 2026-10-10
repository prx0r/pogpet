# CardSpec — the strict card schema + renderer contract

AI chooses content. Renderer builds card. Nothing else is allowed.

> Canonical invariant: for a personalised card request, the external
> agent supplies person + occasion + vibe. OddHobb chooses and completely
> executes one curated template. The only customer-facing render outputs
> are FRONT, INSIDE, BACK. No external agent may design layout or invoke
> lower-level card composition tools.

## CardSpec v1 (the only object the agent may produce)

```json
{
  "template_id": "birthday_4photo",
  "occasion": "birthday | christmas | general",
  "subject_name": "Dad",
  "recipient_name": "Dad",
  "cover_photo_ids": ["pho_abc123", "pho_def456", "pho_ghi789", "pho_jkl012"],
  "cover_headline": "Happy Birthday, Dad!",
  "inside_left_mode": "blank",
  "inside_right_message": "Happy birthday to the person who took golf far too seriously.",
  "inside_signature": "Ben & Peter",
  "tone": "dry"
}
```

Field map to the stored spec: `template_id`→`template`, `cover_photo_ids`
→`photos[]`, `cover_headline`→`headline`,
`recipient_name`→`recipient`, `inside_signature`→`sender`,
`inside_right_message`→`inside.right.message`. `tone` and `occasion`
steer selection only — the renderer never reads them.

## Hard limits (rejected at save, not warned)

| Field | Max | Why |
|---|---|---|
| `cover_headline` | 40 chars | middle title band, one auto-fit line |
| `recipient_name` | 60 chars | byline slot |
| `inside_signature` | 40 chars | centred handwritten signature |
| `inside_right_message` | 240 chars | right page fits at M size minimum |
| `inside_left text` | 160 chars | left note only |

Anything outside the schema — layout, fonts by file, sizes, colours by
hex, panel counts, logo placement — is rejected. Fonts are registry ids
(`figg_card_fonts`), colours are `ink|soft|accent`, sizes are `S|M|L`.

## The five locked birthday templates (archived, not agent picks)

| ID | Photos | Front |
|---|---|---|
| `birthday_arch` | 1, arch slot in balloon art | balloons + cake art, serif headline band |
| `birthday_dots` | 1–3, circle slots on a dot field | dot pattern, bold headline band |
| `birthday_news` | 1, framed slot under masthead | red masthead, photo frame, flat headline band, ticker foot |
| `birthday_gold` | 1, medallion slot on confetti | gold-ring portrait, serif headline band |
| `birthday_wall` | 2–5, white-bordered grid | photo wall, solid headline band |

These render for backwards compatibility (old revisions, the UI editor)
but no agent path may offer them: `oddhobb_make_card` and
`oddhobb_deal_cards` choose the canonical product. The older generic
templates (`portrait`, `breaking_news`, `game_winner`, `awards`,
`christmas`, `family`, `typography`) are likewise archived, not picks.

## The canonical product: `birthday_4photo_title_v1`

One rigid card. 5×7 folded portrait. Exact zones in 1500×2100 trim px
(`CANONICAL_ZONES` in `backend/card_scenes.py` — code is the master).
The founder's geometry, never to be "improved" by an agent:

- top row: 2 photo slots, 602×560, 28px corners
- MIDDLE: title-art zone 930×320 (generated transparent PNG with a real
  alpha channel, or house-serif fallback on one auto-fit line)
- bottom row: 2 photo slots, 602×560
- footer: bare signature only, never prefixed, inside the safe margin
- inside: blank left page; right page has the message block, a centered
  handwritten signature, and nothing else — brand lives on the back only
- back: quiet logo + URL

Tighter caps than generic (rejected at save): headline 40, message 240,
signature 40, exactly 4 photos, vibe from the 8 frozen strings.

## The fullbleed product: `birthday_fullbleed`

No photo slots, no PIL composition. Art is attached per revision (agent-
generated or third-party) and stored owner-scoped; live type is set by the
renderer in real fonts. Same tight caps (headline 40, message 240,
signature 40). Per-field baked/live flags: the headline may be baked into
the front art (integrated lettering is the price of admission — eye-QA the
spelling, it can never be edited without new art); message and signature
are ALWAYS live. Front art 5:7, inside art 10:7, 800px short-edge floor,
YuNet face presence on the front (flat rejects 400, illustrated near-miss
warns). Attach never mutates — every attach mints a new revision. Without
front art, `make_card` returns 409 `art_required` — never a silent collage.

Art direction lives in `ART_DIRECTIONS` (`backend/card_scenes.py`): style,
scene grammar, palette, and negative instructions per template. That plus
the validation gate plus the live-type renderer is the whole prompt-
template system — nothing else is stored.

## The two photo doors

Real photos enter through one of two doors, never both on the same card.
The slot door pastes the actual photo into the composition (the photo
line: canonical 4-photo and birthday set). The reference door sends the
photo to the generator as the identity input (Kontext `image_url`, Qwen
`images[]`, Ideogram character reference) while the filled art-direction
prompt rides alongside — the model repaints Dad inside the art instead of
cutting him out (`reference_prompt()` fills the strings; the Qwen adapter
already accepts reference images, staged behind its key). Attach-art then
validates the result exactly like agent-supplied art. Solo portraits only
through either door — group shots confuse likeness and slots alike.

## The painless path: deal four

Nobody wants to operate the pipeline; they say "card for Dad" and pick
from four. `oddhobb_deal_cards` is that call: one brief, four distinct
templates with four distinct copy angles, four proof_urls. Templates are
the variety engine — reuse is the point, not a compromise. The human opens
the proofs, picks one, edits it, buys it. Illustrated variety joins the
deal the moment a provider key exists; until then the deal is the photo
line, which costs zero.

## Renderer contract (deterministic, no AI)

```
CardSpec → validate (schema + photo ownership + face-crop gate)
         → front.png / inside.png (spread) / back.png (separate surfaces)
         → preview_triptych.png (fixed 3-panel: front | inside | back, one height)
         → listing_4up.jpg (legacy 2×2 collage of the four faces)
         → print.pdf (Prodigi single file, preflighted)
```

Surface-first: the front is never a subpanel inside a larger preview
canvas. The triptych is the default glance for humans and agents; the
2×2 listing stays as a secondary view only. Every mutation mints a new revision. Every view URL carries its revision
(`/cards/<id>/r<rev>/…`) so nothing goes stale. Checkout pins a revision
and 409s without a passing export render. Photo zones honour crop/focus;
the crop is echoed in the scene spec so agents can verify instead of guess.

## The canonical six (card actual.md)

Person + occasion + vibe in, finished buyable products out. No layout,
no fonts, no composition tools on this path:

| Capability | Tool | Notes |
|---|---|---|
| people | `oddhobb_people` | subjects + profiles, existing |
| recommend | `oddhobb_recommend` | rank published recipes, compile top 3 |
| make | `oddhobb_make_card` | one canonical card, full renders |
| variants | `oddhobb_variants` (+`oddhobb_deal_cards`) | same recipe, new vibe/copy/photos |
| get | `oddhobb_get` | status + faces + triptych + print PDF |
| buy | `oddhobb_checkout_card` | pins revision, Shopify draft, £2.99 |

Everything else card-shaped in MCP/REST is machinery: reachable with the
caller's own key, never anonymous, never the documented path. The first
published recipe is `birthday_four_photos_party_title_v1`
(`recipes/`). New recipes ship as new immutable versions, never edits.
