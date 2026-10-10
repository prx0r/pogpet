# oddhobb.device.v1 — provider-independent device contract

A device manifest (devices/<id>.device.json) declares:
- device_type, version, template (the studio template it was built from)
- commands: name → {description, params: {name: {type, required, enum|min|max|default, clamp: true|false}}, timeout_ms, permissions: [integration ids allowed]}
- events: name → payload schema
- safety: firmware-side bounds the runtime enforces whatever the caller asks (never agent-overridable)
- integrations: which adapters may expose it (muse, mcp, pogtown, home_assistant, studio_sim)

Result shape for every call, on every adapter: {"ok": true, "payload": {...}} or {"ok": false, "error": "...", "hint": "..."}.
(Deliberately the same shape as Muse link.result, so the Muse adapter is a pass-through.)

The capability runtime (sdk/runtime.py) is the only thing that touches hardware or the simulator.
Adapters translate transport only: they never add behaviour, so one trace gives one output on every adapter.
