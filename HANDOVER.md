# HANDOVER — next session: freeze review (Dad's 5 cards await verdict)

> **Status:** recipes/ + compiler + canonical six MCP tools live and
> verified on oddhobb.com (98 full-tier / 6 public). Dad's profile
> produced 5 finished export-ready birthday options via recommend +
> variants. Freeze holds: NO new creative features until the founder
> calls those five sellable. Start here: `card actual.md`, then
> `docs/cardspec.md` (canonical six table).

## What shipped (this session batch, all live)

- **Recipes + compiler** (`recipes/`, `backend/recipes/`): schema,
  registry (immutable versions), matcher, compiler (person × recipe →
  design + renders). First published recipe:
  `birthday_four_photos_party_title_v1`. Provenance (`recipe_id`) rides
  revisions through validate.
- **Canonical six MCP**: people / make / change / get / add_media / buy
  (`backend/mcp_server.py`). Public tier is EXACTLY these six
  (verified live); everything else needs the caller's key. Envelope
  responses (`status/summary/artifacts/price/next_actions`), `needs_input`
  states instead of errors, unsigned previews allowed, signer enforced
  at buy. Auth args optional (Bearer → key → anon).
- **Card resets folded in**: middle-title geometry restored + golden
  tests, fullbleed attach lane + YuNet face gate, triptych default,
  solo-first photos, relationship labels (father→Dad), bundle retry on
  busy queue, edit auto-renders, gallery is one canonical card,
  rail previews with viewer photos, stock family seeded (Chris+Cathy
  demo copies, revocable), shelf/reroll/deal endpoints.
- **50-customer auth**: per-customer + per-agent keys (`fagg_`, grants
  cards:read/create/order), bridge routes keyed callers to full tier,
  owner-from-key enforcement, secrets scrubbed from all logs, master
  token rotated + operator-only. Hark agent key minted under
  hark-dad-a7a5cc (grants read/create/order) — revoke at
  `/api/agents/agt_b980f0dc726744859372/revoke` if leaked.
- **Site cleanup**: tab rail overflow fixed, /funnier + /art deep links
  live, gift tiers charge what they show (£5–£20), uploads carry auth +
  owner, sign-in claims work like signup, stale-cache version bumps.

## Verify green

- 98 pytest (card/auth/recipe/golden suites) + 78/78 `scripts/test_site.py`
  (live). 3 pre-existing failures elsewhere in the full suite
  (2 creative-lane, 1 order-dependent family) fail identically on the
  clean tree — untouched, out of scope.
- Live tiers re-verified after deploy: 98 full / 6 public, shelf 200,
  locks law serving, no secrets in fresh logs.

## Next

1. Founder reviews the 5 Dad proofs → sellable verdict (freeze gate).
2. FAL_KEY (or DashScope) approval → own-generator path goes live
   through the existing staged adapters; nothing architectural needed.
3. Per-key rate limits + spend caps (designed, not built).
4. OAuth front door for connectors (spec researched, parked per
   founder call — pasted keys remain the fallback).

---

# HANDOVER — next session: Comedy OS live (blocks → judge → duel page)

> **Status:** theory-aware JokeBlock library built and tested (57+ green);
> duel page live in tree; docs explain relevance to Freaktown + oddhobb.
> Start here: `docs/comedy-os.md`. Tree UNPUSHED.

## What shipped this session

- **27 JokeBlocks** (`templates/blocks/`), 6 canonical anchors v1 with
  timelines, quote banks, premise territories, changelogs; append-only
  history (`log_update` / `supersede_claim` — claims retire, never delete).
- **15 theories** + **12 world operators as functions**
  (`invert_status(A,B)` returns a new state) + 12 question operators +
  GTVH premise fields + jestry S/R/E in the judge.
- **ComedyJudge** (pairwise + swap-agreement + vetoes + ledger taste prior),
  backwards **classifier** (transcript → tags), **regulars** scoring,
  **performance ledger** + catalog `?rank=top`, **meme video** renderer.
- **9 validated 4-panel comics** (canonical Claude-5 + mass-culture 4),
  Originals shelf + premise bibles, Halloween lore pack with source_lore.
- **`/funnier` duel page** (😂 tab): A/B comics voting → preference DB;
  also fixed dead Sharpen-my-bit button (duplicate id bound handler to div).
- **Evergreen tree** (6 trunks / 40 leaves) with event→leaf activation;
  mass-culture gate (6 criteria) for new blocks.

## Relevance

- **Freaktown** built the delivery compiler today (`comedy/`); we are its
  material mine. Contract: our premises stage in their director, our
  theory scores feed their evaluator, our regulars become their cast,
  their stage returns delivery traces our ledger can't get from socials.
- **oddhobb.com:** duel page trains the judge; Originals monetize winning
  premises; personalization runs on voted weights; news_vs_discourse is
  the store's voice on current events.

## Next

1. Keys: FAL_KEY (plates) → OPENROUTER_API_KEY (jev + writers) → X API
   (auto-post; manual until then, log post_ref).
2. First weekly loop: approve 2–3 blocks → 5 comics → post X → ledger →
   reweight. Rebrand Day-1 + 2020-box ready first.
3. Splat rooms (MARBLE_API_KEY), delivery harness (DASHSCOPE), corpora
   mining (shakedracor/romdracor/Molière) — all parked, all specced.
4. Push when owner says go (37 files in tree).

---

# HANDOVER — next session: meme engine live, Originals shelf opens

> **Status:** lore-anchored premise system built, performance loop wired,
> strip-to-video renderer ready. Detail: `docs/meme-engine.md`.

## What shipped (in tree, unpushed at handover time)

- **Originals shelf:** `templates/original/` (house cards you can just buy —
  no photo needed) + `original` style in `templates/catalog.json` (Cards tab
  renders the rail automatically) + first Original `superintelligence_rebrand`.
  Premise bible verbatim: `docs/original-premise-bible.md` (80% premise rule,
  8 mechanisms, taxonomy, 20 seeds).
- **Halloween lore pack:** `templates/premises/halloween_families.json` —
  8 families, 30 premises, every one with a `source_lore` object (real event,
  exact phrase, date, community, recognition). Claude 15–20%, digestible mask,
  less-tame successor, DEPRECATED exit interview, permission loop, HF board
  lore, all 10 robot strips with format tags. `pumpkin_hallucination` dropped
  per founder call (motif repetition, no mechanism).
- **Performance loop:** `backend/creative/performance.py` (append-only JSONL
  in gitignored `data/`, engagement = likes + 5×shares + 3×profile-taps +
  views×completion) + `GET /api/creative/catalog?rank=top` (no signal =
  identical order) + `scripts/meme_reweight.py` weekly table + snapshot.
- **Strip-to-video:** `backend/meme_video.py` — panels + captions → 1080×1920
  MP4 (push-in, deadpan VO via existing tts, burned captions, text never in
  plates). Splat rooms slot in later; assembly doesn't care.
- **Tests:** `tests/test_meme.py` + `tests/test_originals.py`; 104 passed
  with viral/creative suites.

## The wedge: meme creation platform

Premise packs are the meme templates, the renderer is the meme generator,
the ledger is the curation — and every platform (X, TikTok, IG, YouTube) is
a tester, since one strip costs nothing extra to post everywhere. Public
taste trains the weights; the site's personalization engine runs on them.
Creators rent the engine later (vision house rules already cover it: $1
remix royalty, provenance-gated, suppliers invisible). Comics establish
taste; personalised cards monetize it.

## Next

1. `FAL_KEY` approval → fal render path (Ideogram 4 / Recraft V4.1, text-free
   plates) so strips generate straight into Originals.
2. Post first Halloween strips (X single image first, winners get video).
3. First ledger rows → first reweight actually moves.
4. Splat rooms still parked behind `MARBLE_API_KEY`.
5. Matcher scoring boost from engagement (ledger → matcher, catalog hook done).

---

# HANDOVER — next session: brand split live, shelf + plugin + viral loop

> **Status:** OddHobb owns identity, Pogtown owns world (`vision/brand-split.md`).
> Handoff wired, plugin pushed, honesty pass done. Detail below.

## Where we are

- **Vision frozen:** `vision/validatedvision.md` (founder word-for-word + 9
  distilled decisions), `vision/brand-split.md` (identity vs world, one
  graph, one plugin, graduation, human-agent games). 17-file `vision/`
  folder holds the archive.
- **Shelf honest:** 13 live / 10 soon, contracts on all 23 lines + 7 card
  templates, makr3d + printie normalized, 9 own masters watertight.
- **Money real:** Shopify drafts with invoice URLs (token auto-refresh),
  gift packs by budget, Nibble demo friend, friend-derived gifts on shelf.
- **Viral loop:** perform renders + cuts + share (?ref= starters), pogtown
  joke MCP writing through ours, video widget for ChatGPT.
- **Plugin:** 57 MCP tools, openapi.json, chatgpt-plugin bundle, GPT
  instructions, buyer test script, skill. Custom GPTs retire Dec 11 —
  migration path ready.
- **Perform handoff:** stage success says "alive now, send to Pogtown".

## Next

1. Cut buttons on feed UI; funnel numbers.
2. Samples + fit checks for the 7 nearly-there lines; clog adapter.
3. Splat backdrop (Marble key), Qwen voices (HF token).
4. Pog.town doorway when pull justifies it; auth stays Continue with OddHobb.
5. Matcher shelf-wide (asset-filters part 3).

---

# HANDOVER — next session: viral video loop (cuts UI + funnel numbers)

> **Status:** freaktown patterns integrated, Qwen realtime 3.8 wired with
> edge fallback, clip planner live with rendered cuts. Detail:
> `docs/video-integration.md`. Prior sessions below are background.

## Live since last time

- `backend/qwen_voice.py` — Qwen3-TTS via HF Inference, token env-only;
  `qwen:iris`/`qwen:hero` in `/api/voices` (flagged until `HF_TOKEN`).
- `backend/clips.py` + `POST /videos/<id>/clips` (plan or render) +
  `GET /videos/<id>/clip/<cut>` — best-20s proven serving.
- Share links, starter meshes on referral, prompt+script on rows (earlier).

## Next

1. Cut buttons on the feed UI (API renders, UI doesn't expose yet).
2. Funnel numbers: share → signup → starter → upload → sets.
3. Comedy-club splat behind greetings (needs `MARBLE_API_KEY`).
4. Laugh-density windows when judging exists.

---

# HANDOVER — next session: companion launch + Dot standup shareables

> **Status:** companion ingestion shipped (`9cdc3ea`). Screenshot sources,
> multiview clients, print split, rig spec, dot_standup preset all live.
> Watermark-domain bug fixed (was 500ing every video).

## Next steps

1. **"Bring your AI to life" onboarding** — screenshot upload UI copy +
   flow (upload → meet in 3D → Pogtown vs physical choice). Backend ready.
2. **First companion mesh** — needs Meshy spend approval: multiview
   prototype (6cr) → multi-image build (30cr) on a real Dot/Muse screenshot.
3. **Dot-standup distribution** — share links + watermarked feed clips;
   pogtown performer binding per `docs/character-rig.md`.
4. **Print side** — repair API call before `export_print_bundle`; first
   jibbit/keyring from a companion mesh; MAKR3D sample per thesis rule.
5. **Still open from before** — first splat (comedy night) needs
   `MARBLE_API_KEY`; wind indicator geometry; HF_TOKEN for Qwen voices.

---

# HANDOVER — next session: first splat (comedy night)

> **Goal:** generate the first Marble room (comedy night) and wire it as the
> greeting/episode venue. Then, in order: presidential speech, sports press
> interview, red carpet, talkshow.

## Prereqs (nothing stored yet)

- `MARBLE_API_KEY` (platform.worldlabs.ai, NOT the Marble app). $5 min pack.
  Ask-first + `data/marble_credits.jsonl` ledger per `backend/marble.py`.
- Client: `backend/marble.py` already speaks generate/poll/export/balance.
- Docs mirrored: `~/marble-docs/` (pricing, generate/get/export, SPZ scale
  formula, Blender import via KIRI/Reshot).

## Room queue (one $1.20 gen each, plain marble-1.1, text prompt)

1. **comedy night** — brick wall, spotlight cone, mic stand, empty stool.
2. **presidential speech** — curtain, generic flags, wooden podium (parody-safe).
3. **sports press interview** — sponsor wall (ODDHOBB/MAKR3D/PET FC), table edge.
4. **red carpet** — step-and-repeat wall, rope barrier, flash glow.
5. **talkshow** — desk, two chairs, warm practicals, skyline backdrop.

Draft ($0.15) first for composition, full build once, reuse forever.
Metric scale metadata → seat meshes at true size (formula in marble-docs).

## Wire-up after generation

- Backdrop PNG into `data/rooms/<id>.png` (rooms endpoint reports live).
- Splat via KIRI/Reshot into Blender for mesh-inside lighting tests.
- Greetings/episodes take `room=` already — no API changes needed.

---

# HANDOVER — session 2026-10-04 (wearables engine · masters hunt)

> **Status: CURRENT** — wearables v2 engine installed + proven; masters are
> the blocker. Prior session below (2026-10-02) is background.
> **Focus going forward:** premium santa/jacket masters → v2 product proofs.

## Wearables engine (installed from R2, additive only)

- Source: `r2:blog-video-assets/uploads/oddhobb-wearables-engine.zip` (28 KB,
  reviewed module-by-module: clean, no network/secrets in runtime path).
- Installed at repo root: `wearables/` (target/headwear/garment/prop/
  hardware/QC/compiler/runner), `scripts/wearables_{cli,register,seed_demo}.py`,
  `tests/test_manifest.py`, `docs/wearables-engine.md`, `INTEGRATION_SNIPPET.py`.
  Its pytest passes; brick + demo-candle + cake-spikes smoke compose works.
- Two engine bugs fixed in-tree: garment solver pushed shells 5–30 mm INSIDE
  (hull winding + added normal-free clearance guarantee in
  `wearables/garments.py`); engine's own head socket sat on the forehead, so
  `data/anchors/chibi-figure-hook.wearables.json` carries our proven seat
  (ring z≈0.196, rest +7.3 mm).
- Proven end-to-end (`/tmp/opencode/oddhobb-xmas-v2.glb`): hat PASS (rest
  +8.6 mm, sunk 0.4%, 0 poke), jacket PASS (0.15% inside). Renders confirm.

## Masters hunt — hat: yes (flawed) · jacket: nothing free found

- **Santa hat: OpenGameArt CC0** (Lucian Pavel) downloaded direct, cleaned,
  registered at `data/assets/wearables/santa_hat/master.glb` (procedural
  master backed up to `/tmp`). Verdict: wrong proportions for the dog
  (tall floppy cone towers) + imperfect texture — usable placeholder, NOT
  premium. Meshy gallery (Santa Hat 67 etc.) is auth-walled; Poly Pizza is
  bot-walled.
- **Jacket: no free isolated dog garment exists** after searching Meshy,
  Poly Pizza, OpenGameArt, CGTrader (paid), Gumroad (email checkout),
  Sketchfab (account), itch.io, Tripo (AI-gated). Realistic routes only:
  (a) owner browser-downloads a Meshy CC0 hat/garment, or (b) approve Meshy
  API generation spend (box key present, balance last seen 942, untouched).
- **Key hygiene:** a Meshy key + R2 credentials appeared in chat. Neither was
  stored (verified: no history file, no /tmp strays, nothing in git). One
  stale Oct-3 `/tmp` key backup from a prior session was found and deleted.
  Data masters + overrides live under gitignored `data/`. Rotate any
  chat-pasted credentials in their dashboards.

## Still live from before

- Fit editor (`site/fit.html` + `/api/fit/placement`) and all 16 fixed
  cream-era product GLBs from the rollout remain live; suite 77/77.
- Stale product stills PNGs + same-URL browser cache items from
  `docs/fit-problems.md` are unchanged.

## Next

1. Land premium santa + jacket masters in `data/assets/wearables/`.
2. Re-run engine compose → verifier → renders.
3. Then: re-render stale stills, `?v=` cache-bust, retire procedural masters.

## Update 2026-10-04 (OGA santa master fitted)

- OGA CC0 hat cleaned (correct `UVMap` layer + texture), registered as
  `santa_hat/master.glb`, `fit.ease` solved to 0.70 for uniform 0.35 scale,
  socket z 0.187 in the chibi override. Engine composes it cleanly.
- Product `/tmp/opencode/oddhobb-xmas-v4.glb` is CORRECT in 4 rendered
  angles (hero/side/back/top): floppy cone, brim on crown, pompom attached.
- Caveat: verifier hat-mode FAILs it (ring-band heuristics assume a torus
  brim; floppy geometry breaks them). Poke-through count is 0 and all
  angles are clean — metric needs a floppy-hat update, product is good.
- Jacket master still open (procedural shell passes; no free premium
  garment found — Meshy gen or owner download).
- **Cribbage pegs (BOARDGAME-PIECES-SET): full mesh hunt exhausted.**
  Thingiverse/Printables/Cults/Sketchfab need logins, yeggi/3dgo/3dsearch
  bot-wall, CGTrader is paid, Gumroad needs email checkout, OGA has nothing.
  Verdict: pegs are lathe-profile hardware — generated 3 exact-spec masters
  in Blender instead (shaft O3.0–3.2 mm sliding fit for 1/8 in holes, all
  manifold, print-ready): `peg_classic` (taper+collar+ball),
  `peg_ball` (oversized ball), `peg_topper_mount` (10 mm cup for a mini pet
  bust = the personalisation slot). Registered as wearables `hardware` via a
  new generic `static_master` generator (`wearables/hardware.py`), proven in
  a dog+santa+peg compose. No free isolated dog jacket exists anywhere
  reachable — jacket master still needs Meshy gen (spend approval) or an
  owner browser download.

---

# HANDOVER — session 2026-10-02 (products · studio · P0 standup)

> **Status: CURRENT** — write-up of everything touched this session.
> **Focus going forward:** products, Blender assets, gift cards.
> Stage / live lipsync / standup video = **parked** (pogtown wedge, not oddhobb P0).
> Detail: `docs/studio.md`, `docs/etsy-p0-p1.md`, `docs/standup-p0.md`.

## Where we are (live)

| Surface | URL | State |
|---|---|---|
| Main site | https://oddhobb.com/ | Running · bridge :8797 · Flask :8798 · MCP :8799 |
| Studio (character select) | `/#studio` | White stage · 3-slot lineup · live GLB · loadout chips · assets grid |
| Products (Etsy tiles) | `/#products` | Lines: ornament · keychain · brick(soon) · one-click order |
| Cards & prints | `/#cards` | PNG mockup tiles (greeting card, mug, poster…) |
| Videos swipe feed | `/#videos` | Vertical scroll-snap feed · light stage bg · audio |
| Exact product photos | `/products.html` | Downloadable 2000px stills + GLB |
| Live stage (PARKED) | `/stage.html` | three.js jawOpen + set editor — **pogtown later** |

Repo: **github.com/prx0r/pogpet** · this session commits:
`a773a7e` studio/products/cards/videos · `0e55e2c` standup polish ·
`17465ee` jawOpen morph + stage · `d901ded` pose-bake video + set editor.

## What shipped (products-focused)

### Mesh → exact product stills (P0)
- Canonical mesh: `data/uploads/chibi-figure-hook.glb` (printed loop in the GLB).
- **`scripts/exact_product.py`** — `--exact` mode: **no props, no metal, no colour grades**.
- Outputs: ornament @ 80 mm + keychain @ 60 mm, white bg, 2000px, QC PASS.
- Public: `/img/prod/prod-*.png`, `/img/prod/kc-*.png`, `/img/prod/chibi-figure-hook.glb`.

### Coat library (P1, free Blender)
- **`scripts/p1_variants.py` / `coat_library.py`** — cream/golden/chocolate/black/fawn/grey.
- Published: `/img/prod/coat-<name>-{hero,front,side,back,loop}.png`.
- Coat = **preview grade** on existing texture — production multi-colour is a live quote.

### Santa hat
- OGA CC0 FBX in `data/assets/hats/oga-santa/`.
- Stills: `/img/prod/santa-*.png` (hero/front/side/back/loop/hang).
- **Publish rule:** only after seat QC on the measured skull (`docs/oddhobb-custom-preview.md`).
- Keychain line does **not** get santa (assets registry).

### Studio system (modular)
- Registry: `config.STUDIO_LINES` / `STUDIO_COATS` / `STUDIO_HATS`.
- Lines carry `assets.hats` / `assets.coats` per product (ornament→santa, keychain→coats only).
- API: `GET /api/studio`, `/api/studio/stills`, `POST /api/studio/customise|order`.
- Products API: `GET /api/products/studio`, `POST /api/products/personalise|order`.
- MCP: `figg_studio_*`, `figg_product_*`, `figg_checkout`.
- Orders table: `orders` → `pending_checkout` (**no charge** until Stripe/Shopify).

### UI
- **Studio:** Wii-style character select (arrows / side thumbs / centre live mesh). No prices.
- **Products/Cards:** Etsy-style tiles. Cards use PNG mockups (`/img/*_70edae28.png`).
- **Videos:** CSS scroll-snap + IntersectionObserver (light RAM). Warm white stage, not black.
- Floating chrome on store tabs (transparent topbar, icons on white).
- Studio **Assets** grid: star / rename / **AI tag people**.

## Stage / video / lipsync — PARKED (pogtown)

**Do not block oddhobb product work on this.**

| Finding | Detail |
|---|---|
| Freaktown no-GPU lipsync | `basic_body.py` emits **`jawOpen` morph**; browser Web Audio → `morphTargetInfluences` (`LipSync.ts`) |
| Our Meshy dog GLB | Had **0 morphs** — freaktown adapter would be `mode: none` |
| Injected morph | `scripts/add_jaw_morph.py` → `chibi-figure-hook-jaw.glb` (+ `/img/prod/`) |
| Live stage | `site/stage.html` — **three.js** GLTFLoader (model-viewer morph API was wrong) |
| Shareable mp4 | `scripts/pose_lipsync.py` — 9 jaw poses + envelope assemble → `data/videos/p0_standup.mp4` (~39s, in feed) |
| Set editor | stage.html lines/voice/name → `POST /api/standup/render` |
| GPU models | Wav2Lip / SadTalker need CUDA — not on this box. P1 later. |

**Decision:** standup/lipsync = **pogtown product** (edit your set → shareable clip). oddhobb keeps the video feed as a thin viewer + existing free video path. Next oddhobb energy = **products, Blender assets, gift cards**.

## R2 / secrets

- New CF token + S3 keys stored in `.env` only (0600, gitignored). **Never print, never commit.**
- Verified: `git check-ignore .env .token data` · staged diffs clean of secrets.

## Products / Blender / gift cards — next

1. **Controlled custom (IN PROGRESS)** — coat colour + pattern, hat ids, gift card
   form, MCP full chain. Spec: `docs/studio-custom.md`.
2. **Gift card** — live line `gift_card` (£25 default; £10/£25/£50). Digital fulfilment.
3. **Blender asset library** — hats already: OGA santa + Khodrin xmas_hat under
   `data/assets/hats/`. Patterns via `scripts/coat_retexture.py` (spots/stripes/fairisle).
4. **Production quotes** — attach Prodigi/Makr3D SKUs so prices flip EST → LIVE.
5. **Listing pass** — `render_product.py --size 2000` into figg-studio templates.
6. **Santa seat QC** — eyeball `/img/prod/santa-hero.png`; publish gallery only if it sits.
7. **Shopify checkout** — draft orders via `POST /api/products/order` `fulfil:true`
   (`backend/shopify_fulfil.py`). Creds already in `.env`; needs `write_draft_orders`.
8. **Pattern stills** — `coat-chocolate-spots-hero.png`, `coat-golden-stripes-hero.png`
   published under `/img/prod/`.

## MCP full chain (agents)

```
upload photo → start mesh → figg_mesh_manifest (machine-readable mesh + props)
→ figg_studio_props / figg_product_assets
→ figg_fullchain_personalise_order({line, coat, pattern, hat, qty, fulfil})
→ order + optional Shopify draft
```

Custom is **controlled**: registry ids only (`config.STUDIO_CUSTOM_POLICY`).

## Gotchas

- **No Meshy spend** without asking; ledger `data/meshy_credits.jsonl`.
- **Exact product photos** = canonical mesh only — no metal hooks, no colour grades in the photo.
- **Coat ≠ print SKU** — preview grade; multi-colour is a farm quote.
- **Public MCP** needs bridge token (`.token`); Flask direct needs `API_TOKEN` from `.env`.
- **`/img/*`** serves from `data/productimg/` via bridge — not `site/img/`.
- **Videos feed** public route: `GET /api/videos/feed` (all owners, finished clips).
- **Disk ~90% full** — clean render frame dirs; don’t bulk-download models.
- **No GPU** on this box — Blender CPU only; neural lipsync is cloud/Kaggle later.
- Sibling repos (freaktown etc.) are **read-only**; all writes in figgsite.

## Commands

```bash
cd /home/ubuntu/figgsite
./serve.sh                          # bridge + Flask
set -a; . ./.env; set +a; python3 -m backend.mcp_server   # MCP :8799
cloudflared tunnel --config ~/.cloudflared/figgsite.yml run figgsite

# exact product stills (0 credits)
blender --background --python scripts/render_product.py -- \
  --in data/uploads/chibi-figure-hook.glb --out data/marketing \
  --size 2000 --bg white --shots exact --exact --scale-mm 80

# coat library
python3 scripts/p1_variants.py

# public checks
curl -s -o /dev/null -w '%{http_code}\n' https://oddhobb.com/#products
BTOK=$(cat .token)
curl -s "https://oddhobb.com/backend/api/products/studio?owner=anon&token=$BTOK" | head -c 200
```

## Money

- Meshy: 42 cr spent historically; live balance last seen ~1020. **Ask before every call.**
- Studio/products/orders: **0 credits**. Orders reserve intent only.
- Renders: Blender/CPU only.

## Read first

1. This file
2. `docs/studio.md` — studio + products contract
3. `docs/etsy-p0-p1.md` — Etsy P0/P1 + exact-photo rules
4. `docs/standup-p0.md` — lipsync research + **parked** stage path
5. `docs/oddhobb-custom-preview.md` — coat/hat/customise plan
6. `AGENTS.md` — money rules, sibling-repo boundaries
