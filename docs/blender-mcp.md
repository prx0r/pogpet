# Blender MCP compatibility — we don't build it, we feed it

> Reference clone (read-only, not vendored): `~/refs/blender-mcp`
> (`kleer001/blender-mcp` — 175 tools, 25 domains, integration-tested on
> Blender 4.2 LTS, which is our `~/blender` build). Socket `localhost:9334`.

## The split

- **BlenderMCP** drives Blender: import, model, boolean, export, render.
- **OddHobb MCP** owns the design space: contracts, bases, validation,
  save, order. It never touches a viewport.

Run both MCP servers in the same client (Claude Code, Cursor, OpenCode).
The model pulls the contract from us, models in Blender through them, and
validates back through us. Neither side duplicates the other.

## Setup (once, on a machine with a display)

```bash
git clone https://github.com/kleer001/blender-mcp && cd blender-mcp && uv sync
# Blender: install blender_addon/, enable it, N-panel → MCP tab → Start Server
# client .mcp.json:
{ "mcpServers": { "blender-mcp": {
    "command": "uv", "args": ["run", "--directory", "/path/to/blender-mcp", "blender-mcp"] } } }
```

Headless farm boxes stay on our `scripts/factory/*.py` headless path —
same contracts, same validation, no viewport needed.

## The handoff loop (example: golf marker for Dad)

```
1. ours:  figg_blueprints → golf_marker contract
          (locked: dia 24mm, thickness 2mm, flat top; envelope 24×24×4)
2. ours:  figg_design_base(line=golf_marker) → master STL
          (bridge-gated: append ?token=<bridge-token> to download)
3. theirs: import_file(path) → text emboss "DAD" inside top_face zone
          → boolean union → export_file(STL)
4. ours:  figg_design_validate(line, dims, material, text)
          → feasible + makr3d/printie costs
5. ours:  figg_design_save → design_id → figg_design_order
```

Steps 3 is theirs, everything else is ours. The contract is the shared
language: locked interfaces and envelope in, manifold STL out.

## Tool map (theirs → our pipeline stage)

| BlenderMCP | Our stage |
|---|---|
| `import_file` | loads our `design/base` STL |
| `create_object` / `execute_python` | emboss text, seat props |
| `add_modifier` + `apply_modifier` | boolean union into the base |
| `export_file` | produces the candidate STL |
| `render_image` / `capture_viewport` | proof stills (like our hero PNGs) |

Validation, pricing, save and order stay on our side — BlenderMCP never
sees money or the shelf.
