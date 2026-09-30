#!/usr/bin/env python3
"""Chibi figure pipeline: photo -> Meshy Creative Lab (prototype -> build) -> GLB.

    python3 scripts/meshy_figure.py --image <url|path> [--name X] [--out DIR]

WHAT IT SPENDS: prototype 6 cr, build 30 cr (36 total). Per AGENTS.md the
*agent* must ask the user before running this; this script assumes permission
was given. Every spend is appended to data/meshy_credits.jsonl with the
`asked` flag, and the balance is read before (free) and recorded after.

Reads MESHY_API_KEY from the environment or figgsite/.env. No key in argv,
no key on disk anywhere else, never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env before backend.config reads it (real env wins).
def _load_env() -> None:
    env = ROOT / ".env"
    if not env.is_file():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v.strip().strip("'\""))


_load_env()

from backend import config, meshy  # noqa: E402

BASE = config.MESHY_BASE                      # https://api.meshy.ai/openapi/v1
# Creative Lab lives one level up: /openapi/creative-lab/figure/v1/…
CL_BASE = BASE.rsplit("/v1", 1)[0] + "/creative-lab/figure/v1"
LEDGER = ROOT / "data" / "meshy_credits.jsonl"
PROTOTYPE_CR = 6
BUILD_CR = 30


class Spend:
    total_before: int | None = None

    @staticmethod
    def _get(url: str) -> dict:
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {config.MESHY_API_KEY}")
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode() or "{}")

    @staticmethod
    def _post(url: str, body: dict) -> dict:
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {config.MESHY_API_KEY}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode() or "{}")

    @classmethod
    def balance(cls) -> int | None:
        """Free endpoint. None on failure (never guess a balance)."""
        try:
            return int(cls._get(f"{BASE}/balance").get("balance", 0) or 0)
        except Exception:  # noqa: BLE001
            return None

    @classmethod
    def log(cls, stage: str, task_id: str, credits: int, source: str, ok: bool) -> None:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "stage": stage, "task_id": task_id, "credits": credits,
            "source": source, "asked": True, "ok": ok,
            "balance_after": cls.balance(),
        }
        with LEDGER.open("a") as f:
            f.write(json.dumps(rec) + "\n")


def poll(task_id: str, label: str, timeout_s: int = 600,
         retrieve: str = "prototype") -> dict:
    """Poll a task until it resolves. Polling is free.

    `retrieve` mirrors the creating endpoint — GET {CL_BASE}/{retrieve}/{id}.
    (GET /openapi/v1/tasks/{id} does NOT exist for Creative Lab tasks.)
    """
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        raw = Spend._get(f"{CL_BASE}/{retrieve}/{task_id}")
        status, err = meshy.normalise_status(raw)
        shown = f"{label}: {status}"
        if shown != last:
            print(f"  [{time.strftime('%H:%M:%S')}] {shown}", flush=True)
            last = shown
        if status == "succeeded":
            return raw
        if status == "failed":
            raise SystemExit(f"{label} FAILED: {err}")
        time.sleep(6)
    raise SystemExit(f"{label} timed out after {timeout_s}s (task {task_id})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, help="public URL or local path")
    ap.add_argument("--name", default="pogpet-figure")
    ap.add_argument("--out", default=str(ROOT / "data" / "tmp" / "chibi"))
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--remove-background", action="store_true",
                    help="ask Meshy to cut the background out of the CONCEPT "
                         "(the webapp default is off; leave it off)")
    ap.add_argument("--prototype-only", action="store_true",
                    help="stop after the concept (6 cr) and wait for approval "
                         "before the 30 cr build")
    ap.add_argument("--resume-prototype", metavar="TASK_ID",
                    help="skip stage 1 and build from an existing prototype "
                         "(no new prototype charge)")
    args = ap.parse_args()

    if not config.MESHY_API_KEY:
        raise SystemExit("MESHY_API_KEY not set — refusing to run")

    source = args.image
    if not source.startswith("http"):
        # Local file: stage it on the zone so Meshy fetches it over http —
        # same path every other premesh consumer uses.
        import premesh
        source = premesh.stage.stage(Path(source).read_bytes())

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    bal = Spend.balance()
    Spend.total_before = bal
    print(f"balance before: {bal if bal is not None else 'unknown'} cr "
          f"| expected spend {PROTOTYPE_CR + BUILD_CR} cr", flush=True)
    print(f"image: {source}", flush=True)

    if args.resume_prototype:
        pid = args.resume_prototype
        print(f"resuming prototype {pid} (already paid for)", flush=True)
        proto = poll(pid, "prototype", args.timeout, retrieve="prototype")
        proto_cr = int(proto.get("consumed_credits") or PROTOTYPE_CR)
        res = proto
        _write_concept(proto, out)
        # ── stage 2 continues below ─────────────────────────────────
        bres = Spend._post(f"{CL_BASE}/build",
                           {"input_task_id": pid, "name": args.name})
        bid = str(bres.get("result") or bres.get("task_id") or "")
        if not bid:
            raise SystemExit(f"no build task id: {json.dumps(bres)[:300]}")
        print(f"build task: {bid}", flush=True)
        build = poll(bid, "build", args.timeout, retrieve="build")
        build_cr = int(build.get("consumed_credits") or BUILD_CR)
        Spend.log("build", bid, build_cr, source, True)
        print(f"build OK — {build_cr} cr", flush=True)
        return _finish(build, out, proto_cr, build_cr, args)

    # ── stage 1: prototype (6 cr) ────────────────────────────────────
    proto_body = {"image_url": source, "name": args.name}
    if args.remove_background:
        proto_body["remove_background"] = True
    res = Spend._post(f"{CL_BASE}/prototype", proto_body)
    pid = str(res.get("result") or res.get("task_id") or "")
    if not pid:
        raise SystemExit(f"no prototype task id: {json.dumps(res)[:300]}")
    print(f"prototype task: {pid}", flush=True)

    proto = poll(pid, "prototype", args.timeout, retrieve="prototype")
    proto_cr = int(proto.get("consumed_credits") or PROTOTYPE_CR)
    Spend.log("prototype", pid, proto_cr, source, True)
    print(f"prototype OK — {proto_cr} cr", flush=True)
    _write_concept(proto, out)

    if args.prototype_only:
        print(f"\nSTOPPED after prototype ({proto_cr} cr). Concept saved. "
              f"Re-run with --resume-prototype {pid} to build (30 cr) once "
              f"you like what you see.", flush=True)
        return 0

    # ── stage 2: build (30 cr) ───────────────────────────────────────
    bres = Spend._post(f"{CL_BASE}/build",
                       {"input_task_id": pid, "name": args.name})
    bid = str(bres.get("result") or bres.get("task_id") or "")
    if not bid:
        raise SystemExit(f"no build task id: {json.dumps(bres)[:300]}")
    print(f"build task: {bid}", flush=True)

    build = poll(bid, "build", args.timeout, retrieve="build")
    build_cr = int(build.get("consumed_credits") or BUILD_CR)
    Spend.log("build", bid, build_cr, source, True)
    print(f"build OK — {build_cr} cr", flush=True)
    return _finish(build, out, proto_cr, build_cr, args)


def _write_concept(task: dict, out: Path) -> None:
    urls = (task.get("image_urls") or task.get("thumbnail_urls") or [])
    if urls:
        (out / "concept.png").write_bytes(_download(urls[0]))
        print(f"  concept image -> {out / 'concept.png'}", flush=True)


def _finish(build: dict, out: Path, proto_cr: int, build_cr: int, args) -> int:
    urls = build.get("model_urls") or build.get("result", {}).get("model_urls") or {}
    saved = {}
    for fmt, url in urls.items():
        if not url:
            continue
        dest = out / f"figure.{fmt}"
        dest.write_bytes(_download(url))
        saved[fmt] = dest
        print(f"  model {fmt} -> {dest} ({dest.stat().st_size} bytes)", flush=True)
    after = Spend.balance()
    print(f"\nSPENT {proto_cr + build_cr} cr this run "
          f"(prototype {proto_cr} + build {build_cr}) | balance after {after} | "
          f"ledger: {LEDGER.relative_to(ROOT)}", flush=True)
    return 0 if saved else 1


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "premesh/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


if __name__ == "__main__":
    raise SystemExit(main())
