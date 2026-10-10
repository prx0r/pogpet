# hwsim: simulate hardware from supplier specs, drive it with any MCP agent

datasheet → part card (cited, human-verified) → card-driven models + firmware on a virtual board → WoT Thing Description → MCP tools.

## Connect an agent
Claude Desktop / Claude Code / Cursor (stdio):
```json
{ "mcpServers": { "oddhobb-hwsim": { "command": "python3", "args": ["<path>/studio/hwsim/mcp_server.py", "--board", "mood_lamp"] } } }
```
HTTP (any MCP client): `python3 studio/hwsim/mcp_server.py --http 8765`, then connect to `http://127.0.0.1:8765/mcp`.
Quick test without an LLM: `python3 studio/hwsim/client.py --stdio list`.
Needs `pip install "mcp[cli]"` (tested with mcp 2.3.0; client.py uses the legacy initialize handshake).

## Tools the agent gets
- Device tools, compiled from the WoT TD by vendored thingwire. These are the same tools the real product will expose: `read_ambient_lux`, `read_device_health`, `do_light_express`, `do_light_set`.
- World tools: `sim_parts`, `sim_state`, `sim_advance`, `sim_set_ambient`, `sim_inject_fault`, `sim_snapshot` (PNG), `sim_bus_log`, `sim_checks`, `sim_reset`, `sim_save_trace`.

## Pieces
- `cards/*.card.json`: oddhobb.partcard.v1. Status goes DRAFT → EXTRACTED (an LLM read the datasheet, with a citation per field) → VERIFIED (a human checked it). bh1750 is EXTRACTED from the ROHM datasheet; ws2812b and esp32c3 are DRAFT.
- `models/generic.py`: card-driven I2C command device, LED chain (decodes the GRB stream), rails (an LDO's input = its output load), and an I2C bus with a transaction log. No part-specific code.
- `firmware/lamp_fw.py`: the lamp firmware against a 4-function HAL (ports 1:1 to ESP-IDF). It has the real BH1750 driver sequence, the expression engine, the safety governor, and fail-safe behaviour on sensor loss.
- `board.mood_lamp.json`: parts, buses, rails, straps.
- `td.py`: oddhobb.device.v1 manifest → W3C WoT TD 1.1.
- `vendor/thingwire/`: MIT, from github.com/thingwire-dev/thingwire (TD → MCP tool compiler). The same TD can drive a real ESP32 through a ThingWire MQTT gateway.
- `wokwi/gen_chip.py`: card → Wokwi custom chip (chip.json + C). This is fidelity level 2: the real ESP32 firmware runs against a chip generated from the same card. Generated and syntax-checked; running it needs wokwi-cli + WOKWI_CLI_TOKEN.
- `tests/test_cards.py`: datasheet conformance (11/11).

## Fidelity ladder
1. hwsim (this): behaviour, bus protocol and power, in milliseconds per run. For agent testing.
2. Wokwi / Renode: the real firmware binary against generated chips.
3. Bench: the real board, with the same trace and the same checks.

## Adding a part
1. Start a new card with the datasheet URL. Extract the interface, registers/opcodes, timing, power and faults, each with a citation.
2. If the part fits an existing model (i2c_command_device, addressable_led_chain), no code is needed. Otherwise add a generic model.
3. Add conformance tests from the datasheet's own worked examples. Mark the card VERIFIED only after a human check.

Sandbox note: localhost HTTP needs NO_PROXY (client.py sets it).
