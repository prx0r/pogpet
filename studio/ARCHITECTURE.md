# OddHobb hardware studio (v0, 2026-10-10)

Prompt a product → design it from real parts → see an estimate → trial it with an agent in simulation → request a quote → order with the human's go.

```
prompt ─► template (templates/*.json: real parts + enclosure + capabilities + invariants)
            │
            ├─► estimate.py ── suppliers/*  (offline rates + live part prices; every line says quote|estimate)
            ├─► simulate.py ── sdk/oddhw.py SimDevice (digital twin of the same parts) ◄── agent uses Device.tools()
            │       └─ invariant checks (power cap, flash < 3 Hz, night brightness) must PASS
            ├─► quote: suppliers.jlc.JLC.quote() via official API (needs approval) else browser quote on jlc3dp.com
            └─► catalog/packs/<SKU> (G01-G14 gates) ─► order (ODDHOBB_ENABLE_ORDERS=1 + human approval token)
```

## Suppliers (suppliers/)
- base.Supplier: estimate() offline/free; upload(); quote() live/free; order() hard-gated.
- jlc.py: JLC Open API (open.jlcpcb.com, POST JSON, HMAC-SHA256 "JOP" header). 3D printing: upload → file/result → calculate → order/create/list/detail/process. PCB: uploadGerber → calculate → audit → order. Access must be APPLIED for at api.jlcpcb.com and is reviewed against order history. Until approved, quote() raises NotConfigured. Endpoint paths come from the public jlcpcb-mcp client, not yet hit live by us. Assembly (PCBA) and CNC have no confirmed API path: use the browser.
- lcsc.py: LCSC live price ladders + stock, no credentials (retail stock, not JLC assembly stock).
- Add a supplier = one file implementing the contract + an entry in catalog/suppliers.json.

## Parts + templates
- parts/<id>.json: one real part (LCSC code, electrical, joints, sim model).
- templates/<id>.json: parts list with roles, power budget, PCB outline, enclosure, agent capabilities, safety invariants.

## SDK (sdk/oddhw.py)
- The agent sees only `Device.tools()` (JSON tool schema) and `Device.call()`. SimDevice implements it from the parts' sim models; RealDevice (to do) implements the same over MQTT/HTTP on the ESP32, so an agent tested in sim runs unchanged on hardware.
- Safety lives device-side (firmware): power limiter, flash-rate clamp, ambient brightness cap. The agent can't override it.

## Status
- Mood lamp template: 12× WS2812B (C2761795), BH1750 (C78960), ESP32-C3-WROOM-02 (C2934560). Sim passes all 3 invariants. Estimate is about $19/unit at 5 units, 27% live-quoted.
- To do: apply for JLC API → plug credentials in via vault; enclosure mesh (diffuser) → real volume; KiCad/EasyEDA schematic + gerber gen; RealDevice firmware; LLM agent in place of ScriptedAgent; more templates (presence sensor, e-ink, haptics).

## oddhobb.device.v1 + one-trace replay (2026-10-10 evening)
- contract/oddhobb.device.v1.md; devices/mood_lamp.device.json (commands, params with enum/min/max/clamp, per-integration permissions, safety).
- sdk/runtime.py: validate → permission → clamp → execute; result shape {ok,payload}|{ok:false,error,hint} = Muse link.result shape.
- adapters/muse.py (link.register commands_v2 + link.invoke/link.result, u32-LE framed; local LoopbackVM only, no live Muse), adapters/mcp.py (tools/list, tools/call), adapters/pogtown.py (character mood → bounded intent).
- replay.py: same 56 s trace through direct/Muse/MCP/Pogtown → identical frame hash; Layer A (10 contract tests), Layer B (strobe attacks, sensor failure).
- Sim found + fixed: (1) black at brightness 1 rendered white; (2) HSV fades through desaturated tones made luminance blips that let a 150 ms toggle attack hit 5 flashes/s → firmware flash governor (min_big_change_gap_ms 400) + dark-end colour hold → 1.5.
- Layer C: blender/bl_replay.py (12 emitters under frosted dome, room light follows lux) + compare_c.py: hue holds (≤10° drift) but this diffuser keeps only 3-29% of the saturation in room light. Model-dependent; needs a bench photo to confirm.
- OPEN (2026-10-10): JLC Open API application not yet made. Offers to user: (1) tinted diffuser + colour pre-compensation for Layer C; (2) datasheet → verified part card → generators (Python twin, Wokwi custom chip, MCP tools), proven on BH1750. Muse adapter is local-loopback only; never touch muse.ai.

## hwsim (2026-10-10 night): supplier spec → simulated board → MCP
See hwsim/README.md. Cards (bh1750 EXTRACTED from ROHM datasheet; others DRAFT) → generic models → firmware/lamp_fw.py on a HAL → WoT TD → thingwire compiler (vendored, MIT) → MCP server (stdio + HTTP) with device tools + sim_* tools. Tested: datasheet conformance 11/11; real MCP client sessions over stdio and HTTP. Findings: 5V rail 459/500 mA at full white (LEDs 379 + LDO-fed ESP32 80 avg); Wi-Fi TX peaks likely exceed it. Never `pkill -f mcp_server` from the shell (it matches and kills the shell).
2026-10-10 18:55: design_* tools added; Hark agent test passed end to end (hwsim/AGENT_TEST_2026-10-10.md). Pick sunrise-c $31.98/unit x5.
