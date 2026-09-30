# Muse — MCP design (agent-first)

> The MCP is the **product contract**. Everything else — `my.oddhobb.com`,
> the catalog, cards — is a client of the same journey this file defines.
> Written 2026-09-30. Usage/connection docs: `docs/mcp.md`. Tool manifest:
> `TOOL_AREAS` in `backend/mcp_server.py` (20 tools).

## Who is Muse

Muse is the agent *someone else's* assistant becomes when it connects to our
MCP — a person opens ChatGPT/Claude/Cursor, connects
`https://mcp.oddhobb.com/mcp?token=…`, and says "make my dog into a
figurine." Muse then drives the same pipeline the website drives. So the MCP
must carry everything a *stranger's agent* needs: identity, guidance, prices,
progress, and hard guards around money.

**Design stance: agent-first, site-second.** If a tool is awkward for an
agent, it's awkward for us too — the site just hides it better.

## The journey is the API

Tools are ordered around what a customer actually does — which mirrors
`my.oddhobb.com`, our most important page (upload → everything):

```
1. arrive        figg_flow(owner)            → stage: empty … ready + hint
2. identify      figg_create_account / figg_login → api_key (shown once)
3. give a photo  figg_upload_photo(path)     → photo_id      [sandbox]
4. make the mesh figg_start_mesh(photo_id)   → job           [SPENDS 6-36 cr]
5. watch         figg_flow / figg_mesh_status → stage: sculpting → ready
6. see it        figg_products(owner)        → every preview, rendered, with URLs
7. choose        figg_catalog / figg_sections → the library (21 products, 5 sections)
8. price it      figg_quote(sku) / figg_check_sku → live money before committing
9. own it        figg_order (…)              → ❌ NOT BUILT YET — see gaps
10. play         figg_acts / figg_perform    → the stage, free tier
```

A complete Muse session is `figg_tools` first (self-description), then the
journey top to bottom. Any tool that *spends* must be preceded by the agent
showing the user what it costs — see Money below.

## Principles

1. **One contract, three clients** — site UI, mobile, agents all speak this
   surface. A capability that only exists in the site UI is a bug in the
   contract.
2. **Progressive disclosure** — `figg_tools` returns the manifest (areas +
   one-line docs). Agents start there, not by guessing tool names.
3. **Hints over errors** — every response carries what-to-do-next
   (`/api/flow.hint` sets the pattern). An agent that gets "bad token" with no
   context wastes the customer's time.
4. **Money is explicit** — credit-spending tools (`figg_start_mesh`) and any
   future order tool must state cost in the tool docstring *and* in the
   response. See `docs/meshy.md` rules: the human always approves the spend.
5. **Identity is per-customer** — everything hangs off `handle` + `api_key`.
   See the session gap below.
6. **Manifest-driven growth** — new tool = function + one `TOOL_AREAS` row +
   a line in the journey table above. Docs and manifest never diverge because
   `figg_tools` *is* the manifest.

## Session & identity (the model to build next)

Today: tools send the server's own env key (`_key()`), and `owner=` is a
plain parameter on read tools — effectively single-operator. For Muse serving
real customers:

- **Recommended:** every customer-scoped tool accepts optional `api_key`;
  when present the server uses it instead of the env key
  (`X-API-Key` already works end-to-end). Muse holds one key per customer
  session, obtained via `figg_login`.
- `figg_create_account`/`figg_login` remain the only key-issuing tools —
  keys are shown once, so Muse must store them (its own conversation state).
- Anonymous flow stays valid: `owner` param without a key works for browse;
  uploads/sculpts should require identity so assets aren't orphaned.

## Known gaps (the honest backlog, in journey order)

| # | Gap | Notes |
|---|---|---|
| 1 | **Per-customer `api_key` on tools** | session model above; touches every tool signature |
| 2 | **Remote upload** | `figg_upload_photo` reads the server sandbox only. Muse gets photos from chat/URL → needs `figg_upload_photo_url(image_url)` (same `intake` QC) |
| 3 | **The rubric** | `figg_assess_photo` — "can we make this?" before spending: rule-based on intake signals first (see `docs/oddhobb-vision.md` §4) |
| 4 | **Preview URLs are gated** | product image URLs need `?token=` to fetch (the site appends it). Either document that Muse must add its token, or return fetch-ready URLs in `figg_products` |
| 5 | **Ordering** | **zero cart/order routes exist.** `figg_quote` prices, nobody buys. `figg_order` (Prodigi order + payment) is the biggest hole in the contract |
| 6 | **Spend confirmation** | convention for `figg_start_mesh`: docstring states cost; response echoes `credits_spent`/`balance_after` (ledger: `data/meshy_credits.jsonl`) |

## Money rules in MCP terms

- Reading is free. `figg_start_mesh` costs Meshy credits (balance via
  `figg_credits`… actually mesh balance lives in `docs/meshy.md` ledger — add
  `figg_mesh_balance` when we expose it).
- The human asked for the spend; the agent must relay cost before calling.
- Every spend lands in `data/meshy_credits.jsonl` with `asked: true`.

## Later: resources & prompts (cheap wins)

- Resource `oddhobb://catalog` — the same registry as `figg_catalog`, for
  clients that prefer resources over tools.
- Prompt `make_my_oddhobb` — a guided template: "ask for a photo, run the
  rubric, propose 3 products with prices, then sculpt."
- These map 1:1 onto existing registries — no new state.

## Change control

1. Journey order in this file is canonical — if a tool doesn't belong to a
   step, it belongs in a different area or doesn't exist yet.
2. `TOOL_AREAS` is the code truth; this table is the narrative truth; CI-less
   check = `figg_tools` count matches the table (20 today).
3. Protocol/version: FastMCP streamable HTTP; session header handled by the
   bridge proxy (`docs/mcp.md`).
