# Hark as the agent: design → simulate → fix → price, MCP only (2026-10-10)
Transport: MCP streamable HTTP (http://127.0.0.1:8765/mcp) plus stdio; 19 tools.

1. design_create sunrise (24 LEDs, 40 mm ring, USB 500 mA) → DRC error: pitch 5.2 mm < 6.5; use ≤19 LEDs or ≥50 mm ring.
2. design_create sunrise (24 LEDs, 60 mm ring) → ok. sim: dawn ramp 1→400 lx with amber light.
   sim_checks FAIL: LED current 385 mA > 380 cap. Root cause: the firmware limiter scaled the idle current too (24 mA on 24 LEDs). Fixed in lamp_fw.py; re-run PASS at 376 mA.
3. Same design: full white only reaches 62/255 per channel on 500 mA. Too dim for the product.
4. design_create sunrise-c (USB-C 1.5 A, cap 1380 mA) → white 233/255, rail peak 1420/1500 mA, stressed → night ramp → night cap 0.12, all PASS (cards still unverified).
5. design_quote ×5: sunrise-c $159.92 ($31.98/unit, 20% live LCSC); MJF variant $201.52 ($40.30/unit) → keep SLA.
6. Bugs found in the system and fixed: failed-DRC designs left simulatable files; server didn't validate args (raw KeyError) → jsonschema on every call; enclosure enum offered fdm with no JLC rate → sla/mjf/wjp.
Open: USB-C 1.5 A only if the charger advertises it (fallback to 380 mA not modelled); CC resistors not in BOM; ~6.7 W LED heat in an 83 cm3 resin dome not modelled; enclosure (65% of cost) is an estimate; no orders placed.
