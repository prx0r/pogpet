# Voice architecture

```text
Browser microphone
       │
       ▼
InworldVoiceClient
PCM16 / 24 kHz
       │ WebSocket
       ▼
local/server proxy
(secret API key stays here)
       │
       ▼
Inworld Realtime
STT + LLM + turn detection + TTS + tool calling
       │
       ├── audio deltas ──> playback ──> speaking animation
       ├── turn events ───> listen/think/idle animation
       └── tool calls ────> tool router ──> website + Bartholomew
```

For production browser deployment, prefer Inworld's short-lived JWT + WebRTC flow when convenient. The included WebSocket proxy is intentionally easy to understand and keeps the permanent API key server-side.
