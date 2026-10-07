# Meshy — custom guide (this project)

> Full docs are mirrored locally at **`/home/ubuntu/meshy-docs/`** (106 English
> pages, start at `INDEX.md`; API reference is `md/en__api__*.md`). Refresh:
> `python3 /tmp/opencode/meshy_docs_fetch.py`. Only *our* conventions live in
> this file — the mirror is not copied into the repo (Meshy's docs are
> copyrighted; it's re-fetchable instead).

## Golden rules

1. **Meshy is genesis only.** It creates the mesh (single image-to-3d, or
   multi-image-to-3d from 3+ REAL photos) and nothing else — no view
   synthesis (angles must be real, enforced by the 3-angle gate), no repair
   (local Blender), no retexture, no animation. Freaktown rule, same here.
2. **Ask the user before every Meshy call.** The key spends real money.
   This includes "harmless" reads except `/balance` (free, no credits) —
   and even that only after the user has said go for the session.
2. **Never write the key anywhere except `.env`** (0600, gitignored). Not in
   docs, not in tests, not in shell history files, not in logs. Never print it.
3. **Record every credit spend** in `data/meshy_credits.jsonl` (gitignored)
   — see [Ledger](#ledger) — and report the delta to the user afterwards.
4. **Verify a key before trusting it:** `GET /openapi/v1/balance` with
   `Authorization: Bearer $MESHY_API_KEY`. A wrong key answers
   `{"message":"Invalid API key"}` instantly. Our backend's
   `"meshy": "live"` in `/health` only means the env var is non-empty — it
   has *not* validated anything.

## Auth and endpoints

Base: `https://api.meshy.ai/openapi/v1` · header: `Authorization: Bearer $MESHY_API_KEY`
(read from the environment; `backend/meshy.py` reads `config.MESHY_API_KEY`).

| Method | Path | Purpose |
|---|---|---|
| GET | `/balance` | credit balance — **free**, use for preflight |
| POST | `/creative-lab/figure/v1/prototype` | chibi concept image from a photo (**6 cr**) |
| POST | `/creative-lab/figure/v1/build` | textured 3D model from a succeeded prototype (**30 cr**) |
| GET | `/creative-lab/figure/v1/prototype/{id}` | poll the prototype — free |
| GET | `/creative-lab/figure/v1/build/{id}` | poll the build — free |
| POST | `/image-to-3D` | generic photo→3D (what `meshy.py` uses without `chibi=True`) |

Other Creative Lab products follow the same `prototype` → `build` shape:
`keychain`, `lamp`, `fridge-magnet`, `vinyl-figure`, `brick-figure`,
`keycap`, `fidget-pixel`, `fidget-collapsible`. Costs and quirks per product:
`meshy-docs/md/en__api__creative-lab-*.md`. Machine-readable:
`config.MESHY_CATALOG`.

## Creative Lab product matrix (2026-10-02)

| Product | Proto | Build | Total | Input | OddHobb use |
|---|---:|---:|---:|---|---|
| **figure** (chibi) | 6 | 30 | **36** | photo | Pet body → ornament/keychain/croc |
| **brick-figure** | 6 | 30 | **36** | photo | Desk brick (~75 mm) |
| **vinyl-figure** | 6 | 30 | **36** | photo | Collector vinyl SKU |
| **keychain** (CL medallion) | 6 | 30 | **36** | photo | Badge relief ~50 mm — *not* our 3D pet keychain |
| **fridge-magnet** | 6 | 30 | **36** | photo | Pet magnet SKU |
| **lamp** | 30 | 6 | **36** | photo | Glowing lamp; Bambu MH001 60 mm fixture |
| **keycap** | 12 | 50 | **62** | photo | Cherry MX 1u · head 10–40 mm |
| **fidget-pixel** | 6 | 30 | **36** | photo | Desk fidget |
| **fidget-collapsible** | — | 6 | **6** | photo | Cheap impulse |

Also: **Image to 3D** (generic GLB), **3D Print multi-color 3MF (10 cr)**,
printability **analyze free** / **repair 10 cr**.

**API paths:** `/openapi/creative-lab/<product>/v1/prototype|build` —
**not** under `/openapi/v1/`. Poll mirrors create path.

## Can we ship with Meshy? **Yes**

| Fulfilment | How |
|---|---|
| **Meshy Order Print** | Their store: print + ship ~2–3 weeks, 24 countries, free ship in US/CA/DE/ES/FR/IT/BR/CN/JP. Keychains ~$39 beta, fixed 50 mm. |
| **Our print farm** | Makr3D / Prodigi — we control price, branding, Etsy listings. |
| **Home print** | Download STL/3MF from Meshy build. |

OddHobb path today: **generate** body with Meshy (or user GLB) → **previews free**
(Blender) → **fulfil** via our farm or Meshy Order Print. Credits are generation
only; physical cost is separate.

## The chibi flow (figure)

```bash
# 1. prototype — 6 cr, returns a concept image
curl -sS https://api.meshy.ai/openapi/creative-lab/figure/v1/prototype \
  -H "Authorization: Bearer $MESHY_API_KEY" -H 'Content-Type: application/json' \
  -d '{"image_url":"'"$SRC"'","remove_background":true,"name":"pogo-demo"}'
#    -> {"result":"<task_id>"}     $SRC = public URL or data:image/png;base64,…
# 2. poll (free) until status=SUCCEEDED, note consumed_credits
curl -sS -H "Authorization: Bearer $MESHY_API_KEY" \
  https://api.meshy.ai/openapi/v1/tasks/<task_id>
# 3. build — 30 cr, chained by input_task_id
curl -sS https://api.meshy.ai/openapi/creative-lab/figure/v1/build \
  -H "Authorization: Bearer $MESHY_API_KEY" -H 'Content-Type: application/json' \
  -d '{"input_task_id":"<task_id>"}'
# 4. poll again -> result.model_urls.glb (+ .obj/.mtl), thumbnail_urls
```

In our code: `from backend import meshy` →
`tid = meshy.create_task(path, chibi=True)` → loop `meshy.get_task(tid)` →
`meshy.normalise_status(raw)` → `meshy.extract_artifacts(raw)`.

### Two path facts that cost a failed run each (verified 2026-09-30)

1. **Creative Lab is NOT under the `/v1` API-version segment.** Create/poll
   at `https://api.meshy.ai/openapi/creative-lab/figure/v1/prototype` —
   prefixing `/v1` (`/openapi/v1/creative-lab/…`) returns
   `404 NoMatchingRoute`. Generic endpoints (`/balance`, `/image-to-3D`)
   *are* under `/openapi/v1`.
2. **Polling mirrors the create path.** `POST …/prototype` →
   `GET …/prototype/{task_id}`; `POST …/build` → `GET …/build/{task_id}`.
   The classic `GET /openapi/v1/tasks/{id}` does **not** exist for Creative
   Lab tasks (`NoMatchingRoute`), despite the docs saying "poll the Get a
   Task endpoint". Also: the task payload puts `consumed_credits`,
   `image_urls`, `model_urls` at the **top level**, not under `result`.

### Gotchas that cost money if you miss them

- **The build endpoint only accepts prototypes created with the same API
  key.** A prototype made in the webapp returns `404` at build time — the
  6 cr is spent and you cannot chain it. Always do both stages through the API.
- A failed *prototype* charges only 6 cr (the build never starts). A failed
  *build* has already charged 30.
- Keycap is the exception to `input_task_id`-only builds (needs
  `candidate_id`); figure does not.
- Task polling is free — poll, don't re-fire the request to "check".
- Image limits: `.jpg/.jpeg/.png/.webp`. Feed it the **premesh** output
  (`premesh` recipe `meshy`: transparent, ≥1024, subject only) — that is
  exactly the input shape this endpoint wants.
- Rate/credit limits are per key; a key can carry its own monthly cap set in
  the Meshy dashboard.

## Ledger

Append one JSON line per spend to **`data/meshy_credits.jsonl`** (inside
`data/`, which is gitignored — never move it into tracked files):

```json
{"ts":"2026-09-30T14:02:11Z","stage":"prototype","task_id":"…","credits":6,
 "source":"pixabay:2706681","recipe":"meshy","asked":true,"balance_after":1234}
```

`stage` = `prototype|build|image-to-3d`; `credits` = the `consumed_credits`
Meshy reports on that task; `asked` must be `true`. Before any run, read the
file to show total spend this project; after, report the delta.

```bash
python3 -c "import json,pathlib; p=pathlib.Path('data/meshy_credits.jsonl');
print(sum(json.loads(l)['credits'] for l in p.read_text().splitlines()) if p.exists() else 0, 'cr spent')"
```

## Spending without spending

`MESHY_API_KEY` empty → `backend/meshy.py` synthesises a valid GLB
(`is_stub()`), so the whole pipeline, fan-out, stage and print paths stay
testable for free. To sandbox a session, empty the var and restart Flask —
`/health` will honestly report `meshy: stub`.
