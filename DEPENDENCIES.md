# Dependencies NOT in this repo

Everything below must exist on the box (or service) for figgsite to run.
Nothing here belongs in git. If you cloned fresh, this is your setup list.

## Python (pip — see requirements.txt)

flask · pillow · numpy · edge-tts · mcp · cryptography.
Blender-bundled extras (`bpy`, `pxr`) come with Blender, not pip.

## System binaries (apt/manual)

| Binary | Used for | Notes |
|---|---|---|
| `blender` 4.2 (`~/blender/blender`) | personalize, stills, previews | 5.0 dir also present; server uses `~/blender/blender` |
| system `blender` 4.0.2 (`/usr/bin`) | fallback only | lacks OpenImageDenoiser — prefer 4.2 |
| `rclone` + `r2:` remote | R2 storage backend | remote holds account keys; reconfigure per box |
| `cloudflared` | tunnels (`~/.cloudflared/figgsite.yml`) | tunnel `figgsite`, zone oddhobb.com |
| `ffmpeg` / `ffprobe` | video mux, meme renderer, clip cuts | any recent static build |
| `node` | router tests, JS syntax checks | v22 used here |

## Secrets (never commit; 0600; gitignored)

`.env` (API_TOKEN, provider keys, SHOPIFY_*, PIXABAY_*, R2/S3 creds),
`.token` (bridge token), `.vault_key`, `~/.qpbot/vault.json`,
`~/.config/gh/hosts.yml`, Cloudflare API tokens, DashScope key (delivery).

## Services (accounts/keys, expiring)

Cloudflare (zone + tunnel + R2 buckets incl. `figgstudio`, `stallshark`),
Meshy (`MESHY_API_KEY` — ask before every call, ledger in
`data/meshy_credits.jsonl`), Shopify (tokens ~24h expiry), OpenAI/OpenRouter
(jev rank + funny writers), Marble (`MARBLE_API_KEY`, $5 pack), Google
OAuth + STT, Etsy (manual P0 — no OAuth on box), Prodigi (mockups; live
key needed for real quotes), Qwen/DashScope (delivery traces, later).

## Runtime state (gitignored `data/`)

sqlite (`figg.db`), uploads, meshes, productimg stills, cards cache, videos,
listings, fixtures (Mum/Dad photos need owner permission), ledgers
(`meme_performance.jsonl`, `comedy_prefs.jsonl`), `data/pogtown/`
(engine imports). Rebuild fixtures via scripts; never commit photos.

## GPU (off-box)

Voice cloning renders on Kaggle/Colab (`HF_TOKEN` in vault). No GPU here;
Blender runs CPU-only. Neural lipsync is cloud/Kaggle or fal.
