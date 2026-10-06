# Avatar Greetings — the video card (spec)

The product that ties the company together: someone who isn't there saying
something only they could say, as a shareable video. Same gifting motion as
the £3.99 card companion, but it talks. Companion to `thesis.md` (one-shot
manufacturing), `roadmap.md`, `docs/variant-engine.md` (takes are variants),
and `docs/video-episodes-roadmap.md` (the compiler this plugs into).

## The object

```text
greeting = speaker (subject mesh/photo + voice) × room × message → MP4
```

- **Speaker**: any subject. Photo circle today (L1), rigged mesh tomorrow.
  Voice: edge-TTS now, Qwen bank clone when `HF_TOKEN` lands (same as episodes).
- **Room**: one backdrop image per venue, generated once, reused forever.
  Launch set: white void (control), comedy club, podium, press room,
  Christmas living room. Marble splat rooms later; backdrops first.
- **Message**: verbatim text (greeting), not a generated set. Roasts and
  bits stay on the comedy path (`talent=comedy`); greetings speak exactly
  what the customer wrote.
- **Share**: vertical MP4 into the existing videos feed, download link,
  watermark until paid — the same model as stills.

## Venues (rooms as authority)

- **Comedy club** — roasts, sets, open-mic disasters. First room.
- **Podium** — resignations, announcements, denials. Parody seals only,
  nothing official.
- **Press room** — sponsor wall, transfer news, Cup-final speeches.
- **Christmas living room** — Eve messages, toasts, "proud of you" (the
  devastating one).
- **White void** — control background. Always available, never renders a room.

Pets get the same rooms: a dog judging you in a human voice from the club
stool is a series, not a video.

## Economics

- Greeting marginal cost today: $0 (edge-TTS + PIL + ffmpeg, same as videos).
- Room backdrops: one image generation each (user-supplied or Marble draft
  ~$0.15). Generated once, amortized over every greeting ever filmed there.
- Marble full rooms ($1.20) only when a room earns it; photo backdrops first.
- Money rules mirror Meshy: ask-first + ledger per paid call. Marble ledger:
  `data/marble_credits.jsonl` (gitignored). No key stored anywhere yet.

## API

```text
GET  /api/videos/rooms                  registry + backdrop availability
POST /api/videos/greeting                {mesh_id, message, speaker_name,
                                          voice, room} → MP4 (video quota)
MCP  figg_greeting                       same, for agents
```

Checkout parity with videos: same quota, same watermark rules, same feed.
`talent=greeting` distinguishes sets from messages in the videos table.

## AR note (not this push)

Tabletop first: brick minifig on the recipient's desk delivering the message.
Portal cards (point at the Christmas card, Dad steps out) reuse the old figg
AR path. No world-scale overlays until tracking drama is solved elsewhere.

## Build order (this push)

1. `backend/marble.py` — ledgered client, stub without key. No spend possible.
2. `config.ROOMS` — five rooms, backdrop paths under `data/rooms/`.
3. `video.make_greeting` — verbatim TTS + room frame + mux. Reuses everything.
4. Endpoints + MCP tool + tests (offline-safe: stub paths + PIL compose).
5. Room backdrops: user generates 1080×1920 PNGs (see workflow below).

## Room image workflow (for the human with the image generator)

Generate one **portrait 1080×1920 PNG** per room, empty (no people, no text —
the speaker circle and captions composite on top):

- `void.png` — skip, it is pure white by definition.
- `club.png` — brick wall, spotlight cone from above, mic stand silhouette
  center-low, empty stool. Warm darks, space in the upper half for the face.
- `podium.png` — dark curtain, two flags (generic, no real insignia), wooden
  podium low-center, spotlight pool. Grave, parody-safe.
- `press.png` — sponsor-wall grid (fake brands: ODDHOBB, MAKR3D, PET FC),
  table edge low. Bright, flashy.
- `xmas.png` — fireplace right, tree left, armchair center-low, warm glow.
  Space upper-center for the face.

Drop finished PNGs in `figgsite/data/rooms/` (gitignored). The rooms endpoint
reports which backdrops exist; missing rooms fall back to void automatically.
