# Video integration — freaktown patterns in oddhobb perform

> Borrowed, not forked. Freaktown owns avatars, judging, rooms, AR.
> Oddhobb owns the shelf, the feed, the share funnel. Nothing here
> duplicates game truth (pogtown) or the Durable Object rooms.

## What came across

| Freaktown shape | Oddhobb form | File |
|---|---|---|
| `QwenTTSProvider` (HF Inference, token env-only) | `qwen_voice.py` (sync/urllib, same endpoint) | `backend/qwen_voice.py` |
| Provider split (Qwen, edge fallback) | `qwen:<voice>` tries realtime 3.8, falls back to edge-tts, `$0` path never breaks | `backend/video.py:tts` |
| Voice bank listing | `qwen:iris` / `qwen:hero` in `/api/voices`, flagged `needs_token` + live bit | `backend/server.py:voices` |
| Clips planner (TikTok 63–75s, best-20/40s, tail) | time-based cut-list, honest about no laugh buckets | `backend/clips.py` |
| Take/share schema | `POST /videos/<id>/clips` plan-or-render, `GET /videos/<id>/clip/<cut>`, share URLs point at cuts | `backend/server.py` |

## What deliberately did not

- RECORD canvas takes + mic/face stems (our clips are rendered, not performed).
- Rooms/LiveKit DO, Ella judging, AR walkouts (parked behind keys).
- Paid renderer tiers (free tier until spend rule lifts).

## Keys still missing

- `HF_TOKEN` — Qwen voices list as unavailable until attached; edge covers.
- `MARBLE_API_KEY` — comedy-club splat backdrop for Dad sets.
- LiveKit trio — voice rooms.

## Next session

1. Cut buttons on the feed UI (share exists, cuts don't render from UI yet).
2. Starter-mesh + first-upload conversion numbers on the viral funnel.
3. Splat backdrop behind greetings once Marble lands.
4. Laugh-density windows when judging exists; until then time cuts stand.
