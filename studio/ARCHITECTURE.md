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
