# CardSpec — the strict card schema + renderer contract

AI chooses content. Renderer builds card. Nothing else is allowed.

## CardSpec v1 (the only object the agent may produce)

```json
{
  "template_id": "portrait | breaking_news | game_winner",
  "occasion": "birthday | christmas | general",
  "subject_name": "Dad",
  "recipient_name": "Dad",
  "cover_photo_id": "pho_abc123",
  "cover_crop": [0.3, 0.3, 0.667, 0.7],
  "cover_headline": "LOCAL DAD STILL REFUSES TO DIE",
  "inside_left_mode": "blank",
  "inside_right_message": "Happy birthday, Dad. Doctors baffled.",
  "inside_signature": "Prior",
  "tone": "dry"
}
```

Field map to the stored spec: `template_id`→`template`, `cover_photo_id`/
`cover_crop`→`photos[0]`, `cover_headline`→`headline`,
`recipient_name`→`recipient`, `inside_signature`→`sender`,
`inside_right_message`→`inside.right.message`. `tone` and `occasion`
steer selection only — the renderer never reads them.

## Hard limits (rejected at save, not warned)

| Field | Max | Why |
|---|---|---|
| `cover_headline` | 60 chars | single band, never wraps past two lines |
| `recipient_name` | 60 chars | byline slot |
| `inside_signature` | 80 chars | signature line |
| `inside_right_message` | 500 chars | right panel fits at M size minimum |
| `inside_left text` | 160 chars | left note only |

Anything outside the schema — layout, fonts by file, sizes, colours by
hex, panel counts, logo placement — is rejected. Fonts are registry ids
(`figg_card_fonts`), colours are `ink|soft|accent`, sizes are `S|M|L`.

## The three locked product templates

| ID | Front | Inside left | Inside right | Back |
|---|---|---|---|---|
| `portrait` | arch photo slot in CC0 birthday art, serif headline band, name byline | blank | message + signature | brand mark only |
| `breaking_news` | red masthead, framed photo slot, flat headline band, ticker foot | blank | message + signature | brand mark only |
| `game_winner` | gold-ring medallion photo slot on confetti, headline band | blank | message + signature | brand mark only |

The other four templates (`awards`, `christmas`, `family`, `typography`)
keep rendering but are not product picks — the agent offers the three.

## Renderer contract (deterministic, no AI)

```
CardSpec → validate (schema + photo ownership + face-crop gate)
         → front.png / inside.png / back.png (spread faces)
         → listing_4up.jpg (fixed 2×2 collage of the three + contact sheet)
         → print.pdf (Prodigi single file, preflighted)
```

Every mutation mints a new revision. Every view URL carries its revision
(`/cards/<id>/r<rev>/…`) so nothing goes stale. Checkout pins a revision
and 409s without a passing export render. Photo zones honour crop/focus;
the crop is echoed in the scene spec so agents can verify instead of guess.
