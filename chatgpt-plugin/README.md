# OddHobb ChatGPT plugin

Migration-proof package: custom GPTs retire Dec 11 2026, plugins are the
replacement. Instructions become the skill, knowledge becomes references,
connected app is our MCP server (custom actions do NOT migrate — the MCP
server is the rebuild, already live).

## Contents

- `SKILL.md` — the instructions (from `docs/gpt-instructions.md`).
- `references/products.json` — all 23 lines with contracts + prices (verified in sync 2026-10-09).
- `references/card-templates.json` — all 14 templates with paper contracts, incl. the 7 canonical birthday recipes (regenerated 2026-10-09).
- Connected app: `https://mcp.oddhobb.com/mcp?token=<bridge-token>`
  (104 tools full tier / 6 public; install doc in `docs/chatgpt.md`).
- Actions spec: `https://oddhobb.com/openapi.json` (28 endpoints).

## Migrate / install

1. Plugin takes this folder: skill + references + connected MCP app.
2. Test with `docs/chatgpt-test.md` (8 buyer blocks).
3. Share privately first; directory submission separately.
