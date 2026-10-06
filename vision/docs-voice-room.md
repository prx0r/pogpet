# Voice room: LiveKit transport + Gemini brain + OddHobb tools (spec)

How mic-on shopping actually works: LiveKit moves audio, Gemini thinks,
our MCP answers. No component does another's job. Docs mirrored at
`~/livekit-docs/` (agent sessions, turns/tuning, tools/MCP, Gemini realtime
plugin, keyterms, pipelines).

## Shape

```text
browser mic ──WebRTC──► LiveKit room (one per shopper)
                              │
                    agent worker (Python, livekit-agents[mcp])
                    ├── realtime: Gemini Live plugin (voice brain, barge-in)
                    ├── tools: MCPToolset → https://mcp.oddhobb.com/mcp
                    │           (guide_open/turn/packs, product_assets,
                    │            personalise, checkout, greeting, cards)
                    └── keyterms: jibbit, line names, motifs (STT bias)
```

- **Transport (LiveKit):** rooms, token route, VAD turn detection, adaptive
  interruption (backchannel vs true barge-in distinguished). We never build
  audio plumbing again.
- **Brain (Gemini Live):** same provider already abstracted in
  `backend/voice_chat.py`. The worker uses the Gemini realtime plugin, not
  our session endpoint — the endpoint stays for direct-browser mode.
- **Hands (our MCP):** first-class `MCPToolset` support (Python). The agent
  calls the ramble flow engine as tools: `figg_guide_turn` for the shopper
  state machine, `figg_guide_packs` for curated packs, checkout/greeting/
  cards for the close. No duplicated logic — the tools ARE the shop.
- **Fallback:** Web Speech rebind + typed input stay. Voice room is
  progressive enhancement, never a gate.

## Ramble flow over voice

1. Room opens → agent greets, asks who/occasion/budget (guide_open).
2. Every turn → `figg_guide_turn`. Interruptions ("yeah, croc jibbit!")
   arrive as barge-in; turn-tuning keeps backchannel ("mhm") from
   re-ranking while true interrupts re-run packs immediately.
3. Photos still upload in-page (voice can't send pixels); agent narrates.
4. Packs read aloud as three picks max; "show me" pushes stills to the page
   via data track; keep/discard by voice updates taste weights.
5. Checkout by explicit confirmation only. No autonomous ordering.

## Keyterms (STT bias list, generated from catalog)

jibbit, clog charm, shoelace, Mahjong, cribbage, domino, TCG, divot,
wind indicator, rummy, slab, topper — product vocab only, rebuilt by a
script from STUDIO_LINES labels + INTEREST_MOTIFS. Prevents the classic
"craft gibbet" mishears.

## Credentials needed (none stored yet)

- `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` (Cloud project or
  self-hosted SFU) — for the token route + worker dispatch.
- `GOOGLE_API_KEY` — already in `.env` (voice brain live).
- Worker host: small always-on process for dispatch; batch renders stay on
  this box. Telephony (SIP Christmas hotline?) parked — same rooms, later.

## Costs

- LiveKit Cloud: usage-based rooms/minutes (see their billing); self-host
  SFU is $0 + ops burden. Decide at volume, start Cloud.
- Gemini Live: ~$0.005 in / $0.018 out per audio-minute. A 3-minute shop
  ≈ 4–8¢. Cheaper than the Meshy credit inside the mesh it sells.
- Our tools cost what they cost today ($0 except Meshy builds).

## Verdict: spec, not spike

A worker file without Cloud credentials is dead code — it can't join rooms,
can't be tested, and rots. Build order: Cloud project → token route
(`POST /api/voice/room`) → worker skeleton (session + MCPToolset + keyterms)
→ turn-tuning pass → pack-readout data channel → site mic button joins room.
Each step is independently verifiable; no step before its credential exists.
