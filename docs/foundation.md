# Foundation — catalog, flow, MCP manifest

> Built 2026-09-30 (round 2 of the to-dos: `docs/todo.md`). Everything here is
> **registry-driven on purpose**: new products, sections and MCP tools are data
> entries, not code hunts.

## 1. The catalog — one registry, three consumers

`backend/config.py` holds the truth in four maps:

| map | holds |
|---|---|
| `PRODUCTS` | mesh-derived products (label, price, source, free) |
| `PRODIGI_PRODUCTS` | printed products (label, price, sku_note, shape) |
| `SECTION_OF` + `SECTIONS` | where a product sits in the rail/subdomains |
| `PRODUCT_EMOJI` / `PRODUCT_BLURB` / `SHAPE_EMOJI` | how a card presents |

**`GET /api/catalog`** merges them into one row list:
`{id, label, price_cents, free, source, section, preview(mesh|prodigi), emoji, blurb}`
plus the section registry. Consumers:

- **site cards** — `site/index.html` fetches it at boot and overwrites the
  inline `EMOJI`/`BLURB` fallbacks, so a product's card text changes in config
  only;
- **shop grid** — `/api/products` (mockups) and `/api/meshes/<id>/products`
  both emit `section` for filtering;
- **MCP** — `figg_catalog` returns the same rows to any agent.

### Adding a product

1. entry in `PRODUCTS` or `PRODIGI_PRODUCTS` (label/price/source…)
2. `SECTION_OF[pid] = "<section>"` (omit → All only)
3. `PRODUCT_EMOJI[pid]` + `PRODUCT_BLURB[pid]` (mesh products) or a
   `SHAPE_EMOJI[shape]` (prodigi)
4. if it needs a mockup: a `shape` in `PRODIGI_PRODUCTS` + renderer in
   `backend/mockup.py`

Nothing else: no frontend edit, no MCP edit.

### The inheritance guarantee (mesh products)

A mesh that was created **before** a product existed must still show that
product — otherwise every config addition silently strands old meshes (and the
sample) until an expensive re-sculpt. `GET /api/meshes/<mid>/products` now
does a set-difference on every read and calls the idempotent
`db.bind_products()` for anything missing, and drops bindings whose product
left the config.

**Proven, not promised:** deleted `comedy_set` from the sample mesh →
re-read → 7 rows became 8 again. Prodigi mockups never needed this (they
iterate `PRODIGI_PRODUCTS` live per request).

### The sample (so nothing renders empty)

`scripts/seed_sample.py` (0 credits, idempotent) plants the demo pet under
owner `anon` — the default for every logged-out visitor:

- photo: the premesh-normalised PNG (1024×682) → `owners/anon/photos/…`
- mesh: `data/uploads/chibi-figure.glb` (our generated dog, 24.9 MB) →
  `owners/anon/meshes/msh_70edae28…/model.glb`, status `succeeded`
- bindings: 8/8 products, set **active**

First shop open for `anon` renders all 13 Prodigi mockups cold (~30 s), then
they're cached in R2. Re-running the script is a no-op.

## 2. The flow — upload → mesh → previews

**`GET /api/flow?owner=`** returns the whole state machine in one call:

```json
{ "stage": "empty | uploaded | sculpting | ready",
  "photos": [...], "meshes": [...],
  "active_mesh_id": "...", "active": {...},
  "catalog_count": 21,
  "hint": "Ready — every product below previews against this mesh." }
```

Stage rules: any mesh queued/running → `sculpting`; an active mesh succeeded →
`ready`; photos but no mesh → `uploaded`; else `empty`.

Client side the loop already existed (upload → spotlight poll → shop renders
every product preview against the active mesh); the foundation adds:

- **previews re-render when the mesh lands** — `poll()` calls `loadShop()` if
  the shop is open, so the grid never shows a stale mesh's mockups;
- the **status base cache resets** on each reload (no stale spotlight prefix);
- everything a client (site or MCP) needs is one `figg_flow` / `/api/flow` call.

Previews render lazily on shop open and are cached in R2 per active mesh —
`/api/products` rendered all 13 in ~4 s first time, then hits cache.

## 3. MCP — manifest-driven tools

`backend/mcp_server.py` no longer sprinkles decorators: functions are plain,
and `TOOL_AREAS` is the single registration point:

```python
TOOL_AREAS = {
  "flow":     [figg_flow, figg_upload_photo, figg_start_mesh],
  "identity": [figg_me, figg_create_account, figg_login, figg_credits],
  "mesh":     [figg_mesh_status, figg_measure, figg_print_export],
  "shop":     [figg_catalog, figg_products, figg_concepts, figg_quote, figg_check_sku],
  "style":    [figg_styles, figg_install_style],
  "stage":    [figg_acts, figg_perform],
}
for fns in TOOL_AREAS.values():
    for fn in fns: mcp.tool()(fn)
```

**Adding a tool = write the function, add it to an area.** `figg_tools`
returns the manifest so clients can introspect the library (20 tools today).

The MCP can now drive the entire product loop, not just read it:

```
figg_upload_photo("dog.jpg")  → photo_id     (sandbox-only: FIGG_UPLOAD_DIR)
figg_start_mesh(photo_id)     → mesh job
figg_flow()                   → stage/progress until "ready"
figg_catalog() / figg_products / figg_quote  → the whole library
```

Security is unchanged and documented in `docs/mcp.md`: server binds
127.0.0.1, bridge gates `/mcp`, uploads are path-contained inside the sandbox
(`resolve()` + prefix check — no `../` escapes).

> Raw-client note: Cloudflare rejects `Python-urllib`-style agents with **403**
> on POST — send a normal `User-Agent` from scripts.

## 4. Verification (2026-09-30)

- `/api/catalog` → **21 products, 5 sections**; emoji/section/preview fields present
- `/api/flow?owner=carol` → `stage: ready`, 3 photos, 3 meshes, hint correct
  (fixed mid-build: the photos table has **no status column** — presence is the state)
- MCP `tools/list` → **20 tools** incl. all five new ones, via the gated public URL
- shop grid refresh hook + catalog merge present in served HTML; inline JS passes `node --check`
- `api.log` — no new tracebacks after the fix

## People: autosort, "who's this?", profiles (the gifting seed)

Uploads group themselves. `photos.person` (nullable, migrated in place) is
the group label; the contract:

- **`POST /api/photos/autosort?owner=`** — difference-hash clustering
  (free, local, PIL-only), union-find at hamming ≤ 12. Unlabeled clusters get
  `Person N` + `needs_name: true`; existing labels stick. Each photo returns
  `{id, mime, r2_key, has_mesh, mesh_id}` so the UI can thumb + spotlight.
- **`POST /api/people/rename` `{owner, from, to}`** — renames every photo
  carrying the old label: the "who's this?" input writes straight to the
  profile.
- **my. renders it**: spotlight = the superstar (renamed "Your star"),
  `#people-grid` = one card per group — name input, photo thumbs, "make star"
  where a mesh exists (reuses the same `activate()` as the roster), "no sculpt
  yet" where it doesn't, "new face" hint where `needs_name`.
- **Why it matters:** a named person *is* a giftee. When custom gifting lands,
  "make one for Nibble" is already a profile with photos, a mesh and a name.

Adding face recognition later swaps only the inside of `autosort` — the
response shape, the rename endpoint and the UI stay identical.
