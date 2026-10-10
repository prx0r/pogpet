# Shopify auth — how OddHobb talks to Shopify

Reference only. **No secrets live in this file.** Real credentials are in
`.env` (gitignored, mode 0600).

> LIVE TARGET 2026-10-09: `byg8sv-p6.myshopify.com` ("OddHobb" — 15
> products). `.env` still points at the dev store
> (`oddhobb-oufybzg3.myshopify.com`) until live credentials land. Do NOT
> treat dev-store drafts/webhooks as production. Status: ODD-CARD-5X7
> £2.99 variant `gid://shopify/ProductVariant/58870309552509` stored in
> `.env` (verified resolving). Still needed: live Admin API token (draft
> orders + webhooks scopes) and live Storefront access token (cart API) —
> without the latter, /api/cart/* answers the exact missing piece instead
> of guessing. History below is the dev store.

Last verified (dev): 2026-09-30 — shop query OK,
13 products active on `oddhobb-oufybzg3.myshopify.com` (GBP).

## Why there is no copyable `shpat_` in the Shopify UI

The app is a **Dev Dashboard** app (the current path — admin-created custom
apps that showed a permanent `shpat_` token in the UI are deprecated).

| Token you might see | What it actually is | Use it for |
|---|---|---|
| automation token (prefix `atkn`) | **App Automation Token** | Shopify CLI deploys only (`SHOPIFY_APP_AUTOMATION_TOKEN`). **Cannot** call Admin GraphQL. |
| client secret (prefix `shpss`) | **Client secret** | Exchanging credentials for an access token. Server-side only. |
| 32-char hex (`2f013467…`) | **Client ID** | Public-ish app identifier; also used in the token exchange. |
| admin access token (prefix `shpat`, obtained programmatically) | **Admin API access token** | The only token that works on `/admin/api/*/graphql.json`. |

Tokens from this flow **expire every 24h** (`expires_in: 86399`). Refresh by
repeating the exchange — no merchant interaction.

## The working flow (client_credentials grant)

```
client_id + client_secret
        │
        ▼  POST https://{store}/admin/oauth/access_token
           grant_type=client_credentials
        │
        ▼
access_token (shpat_…)  ──X-Shopify-Access-Token──►  GraphQL Admin API
        │
        └── expires in 24h → exchange again
```

curl equivalent (values from `.env`, never hardcode):

```bash
set -a; . ./.env; set +a
curl -s -X POST "https://${SHOPIFY_STORE}/admin/oauth/access_token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=${SHOPIFY_API_KEY}&client_secret=${SHOPIFY_API_SECRET}"
```

Response shape:

```json
{ "access_token": "<shpat-style token>", "scope": "read_products,write_products,…", "expires_in": 86399 }
```

Then any Admin call:

```bash
curl -s -X POST "https://${SHOPIFY_STORE}/admin/api/2024-10/graphql.json" \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Access-Token: ${SHOPIFY_ACCESS_TOKEN}" \
  -d '{"query":"{ shop { name } }"}'
```

## Env contract (all in `.env` only)

| Variable | Role |
|---|---|
| `SHOPIFY_STORE` | `oddhobb-oufybzg3.myshopify.com` (no https://) |
| `SHOPIFY_API_KEY` | Client ID — also written to `shopify-app/shopify.app.toml` as `client_id` (not secret) |
| `SHOPIFY_API_SECRET` | Client secret — `.env` only, never toml/git/logs |
| `SHOPIFY_ADMIN_TOKEN` | Optional pre-minted admin token; unused when credentials exist |
| `SHOPIFY_ACCESS_TOKEN` | Latest minted admin token (runtime only in `.env`); script refreshes as needed |

## What the sync script does

`shopify-app/scripts/sync-catalog.mjs`:

1. Reads `SHOPIFY_STORE` + either `SHOPIFY_ACCESS_TOKEN` or client credentials.
2. If no valid token, POSTs the client_credentials exchange above.
3. On GraphQL 401, re-exchanges once and retries (covers 24h expiry).
4. Reads our public feed (`FEED_URL`, default oddhobb shopify.json) and
   upserts products by handle — create sets title/price/media; update
   refreshes copy/price using the existing variant id.

```bash
# dry-run (prints CREATE/UPDATE, touches nothing)
FEED_URL=https://pog.pet/backend/api/feeds/shopify.json \
  node shopify-app/scripts/sync-catalog.mjs --dry-run

# real sync
FEED_URL=https://pog.pet/backend/api/feeds/shopify.json \
  node shopify-app/scripts/sync-catalog.mjs
```

Last real run: **11 created, 2 updated, 13 total**, all ACTIVE with images
and GBP prices.

## Scope note

The app was granted a broad scope set (products, listings, publications,
metafields, files, themes, content, menus, orders, draft orders, customers,
inventory, fulfilments, shipping, webhooks, analytics). That covers catalog
sync, the future `<model-viewer>` metafield path, and later checkout work.
**Google/Pinterest connections** still happen by installing the official
sales-channel apps in the store — our scopes only keep catalog data complete
and published.

## Money safety (re-read this part)

- Admin API tokens **cannot** charge cards, pay vendors, or move payouts.
  There is no payment rail on `X-Shopify-Access-Token`.
- App billing always needs an explicit merchant consent screen an API token
  cannot trigger silently.
- Worst case on a dev store: messy product data (recoverable; sync is
  idempotent by handle).
- **The only real spend path in this project is Meshy** (image-to-3D
  credits; ledger `data/meshy_credits.jsonl`; balance was 1,056 cr).
  Rule: ask the owner before every paid Meshy call. Prodigi only quotes.
- Secrets never go in git, docs, test output, or commit messages.

## Hygiene checklist (verified 2026-09-30)

- `.env` and `.token` are gitignored (`git check-ignore` confirms) and
  mode 0600.
- `git ls-files` + content scan of tracked files: **no** client secret,
  admin token, or automation token.
- `shopify-app/shopify.app.toml`: `client_id` only — no secret/atkn/shpat.
- `.env.example`: placeholders only.
- Runtime logs under `/tmp/opencode/` and `data/`: no credential material.
