# OddHobb CompanyGraph + bobdod

Pattern source: `prx0r/agentcom` `companygraph/` (FACTS / RESOURCES /
CAPABILITIES). Research clone: `/home/ubuntu/refs/agentcom/companygraph/`.

## bobdod

Main helper agent. Customers talk to bobdod in the storefront chat; MCP
clients meet the same identity. Default host — guest archetypes (Buster,
Pogo, …) remain optional moods.

- Config: `HELPER_AGENT` in `backend/config.py`
- Frontend: `BOBDOD` in `site/index.html` (default session host)
- MCP: identity noted in `backend/mcp_server.py`; tool `figg_companygraph`

## Graph

`GET /api/companygraph` (public, bridge-ungated) returns:

| Block | Source |
|-------|--------|
| `company` | brands map, support email, GB |
| `helper_agent` | bobdod record |
| `products` | live `PRODUCTS` + `PRODIGI_PRODUCTS` (20 items, GBP) |
| `policies` | free tier, shipping, personalisation, watermark, payment |
| `resources` | Shopify, Cloudflare, R2, Meshy, MCP |
| `capabilities` | read free; writes approval-gated; order/email reserved |

Products and policies **derive from config** — the graph cannot drift from
the catalog.

## MCP

```
tools/call figg_companygraph  → full graph JSON
```

Read-only. Same permission model as the rest of the MCP (bridge token gate;
FIGG_OWNER/FIGG_API_KEY for writes).

## Tests

`scripts/test_site.py` checks `/api/companygraph` is public, names bobdod,
and lists products + capabilities.
