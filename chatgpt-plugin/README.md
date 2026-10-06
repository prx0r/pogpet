# OddHobb ChatGPT plugin

Migration-proof package: custom GPTs retire Dec 11 2026, plugins are the
replacement. Instructions become the skill, knowledge becomes references,
connected app is our MCP server (custom actions do NOT migrate — the MCP
server is the rebuild, already live).

## Contents

- `SKILL.md` — the instructions (from `docs/gpt-instructions.md`).
- `references/products.json` — all 23 lines with contracts + prices.
- `references/card-templates.json` — 7 templates with paper contracts.
- Connected app: `https://mcp.oddhobb.com/mcp?token=<bridge-token>`
  (55 tools; install doc in `docs/chatgpt.md`).
- Actions spec: `https://oddhobb.com/openapi.json` (14 endpoints).

## Migrate / install

1. Plugin takes this folder: skill + references + connected MCP app.
2. Test with `docs/chatgpt-test.md` (8 buyer blocks).
3. Share privately first; directory submission separately.
