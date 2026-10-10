"""Pipeline: photo -> mesh -> active across every product.

The important property: a Mesh row is written once and every product binds
to *it*. Re-theming for a season re-renders from the same GLB, which is the
whole "upload once, own the character" thing.
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import config, db, meshy, storage


class PipelineError(Exception):
    def __init__(self, message: str, code: int = 400, data: dict | None = None):
        super().__init__(message)
        self.code = code
        self.data = data or {}


def credit_top_up(owner: str, c=None) -> dict:
    """Machine-readable earn/top-up routes for 402 bodies. No invented URLs:
    balance endpoint is real (GET /api/credits/balance), earn route is wired
    (webhook +1 per paid order). Credit-pack product: webhook-ready via
    db.credit_pack_redeem, product page to come."""
    if c is None:
        with db.connect() as c2:
            return credit_top_up(owner, c2)
    return {
        "top_up_url": f"/api/credits/balance?owner={owner}",
        "credits_remaining": db.credit_balance(c, owner),
        "genesis_used": db.genesis_used(c, owner),
        "earn": [
            {"route": "paid product order", "credits": "+1",
             "how": "automatic on Shopify orders/paid webhook"},
        ],
    }


def _local_photo(photo: dict) -> Path:
    """Get the source image locally — staging first, R2 second."""
    sha = photo["sha256"]
    staged = config.LOCAL_TMP / f"{sha}.jpg"
    if staged.exists():
        return staged
    dest = config.LOCAL_MESH / photo["id"] / "source.jpg"
    if not dest.exists():
        try:
            storage.get(photo["r2_key"], dest)
        except storage.StorageError as e:
            raise PipelineError(f"source photo unavailable: {e}", 410) from None
    return dest


def _refund_mesh(mid: str) -> None:
    """Provider-side failure refunds by funding source (genesis|credits|daily).

    Takes the mesh id (not owner): the mesh row records exactly how it was
    funded, so a genesis sculpt restores genesis and a paid-credit sculpt
    restores the credit. Idempotent — safe to call twice. Never raises.
    """
    try:
        with db.connect() as c:
            db.refund_mesh(c, mid)
    except Exception:  # noqa: BLE001 — refund must never fail the failure path
        pass


def _job_payload(c, job_id: str) -> dict:
    try:
        row = c.execute("SELECT payload FROM jobs WHERE id=?", (job_id,)).fetchone()
        return json.loads((dict(row).get("payload") or "{}"))
    except Exception:  # noqa: BLE001
        return {}


def start_mesh(photo_id: str, *, single: bool | None = None) -> dict:
    """single=None (default): auto — single-view iff exactly 1 angle on file.
    single=True: force single-view. single=False: demand 3 angles (400 if short)."""
    with db.connect() as c:
        photo = db.get_photo(c, photo_id)
        if photo is None:
            raise PipelineError("That photo isn't on file — upload it first.", 404)

        # Cache per photo: a usable mesh already exists, so don't burn credits
        # re-sculpting the same picture ("upload once, own the character").
        reusable = c.execute(
            "SELECT * FROM meshes WHERE photo_id=? AND status IN ('queued','running','succeeded')"
            " ORDER BY CASE status WHEN 'succeeded' THEN 0 ELSE 1 END, created_at DESC"
            " LIMIT 1", (photo_id,)).fetchone()
        if reusable:
            return {"mesh": db.dump(reusable), "reused": True}

        # New sculpt = real Meshy credit, so it comes out of the free daily
        # allowance. Cached hits above never reach here and never charge.
        owner = photo["owner"] or "anon"
        day = datetime.now(timezone.utc).date().isoformat()
        # 3-angle gate: same subject, 3+ confirmed photos → multi-image build
        # (better meshes, same 1 credit). Canonical identity is the
        # studio_subjects → photo_subjects graph; the legacy person label is
        # fallback only. Fewer angles needs explicit single:true.
        person = ""
        try:
            links = c.execute("SELECT subject_id FROM photo_subjects"
                              " WHERE photo_id=? AND confirmed=1", (photo_id,)).fetchall()
            sids = {dict(r)["subject_id"] for r in links}
        except Exception:  # noqa: BLE001 — table missing on old DBs
            sids = set()
        if sids:
            group = c.execute(f"SELECT DISTINCT photo_id FROM photo_subjects WHERE subject_id IN "
                              f"({','.join('?' * len(sids))}) AND confirmed=1",
                              tuple(sids)).fetchall()
            angles = [dict(r)["photo_id"] for r in group]
        else:
            try:
                person = (photo["person"] or "").strip()
            except (KeyError, IndexError, TypeError):
                person = ""
            if person:
                group = c.execute("SELECT id FROM photos WHERE owner=? AND person=?",
                                  (owner, person)).fetchall()
                angles = [dict(r)["id"] for r in group]
            else:
                angles = [photo_id]
        multi = len(angles) >= 3
        if single is None:
            # Single-photo onboarding default: sculpt single-view when only
            # one angle exists; multi-view upgrade later for print products.
            # Two angles still needs an explicit choice (400 below).
            single = len(angles) == 1
        if not multi and not single:
            raise PipelineError(
                f"Only {len(angles)} angle(s) of "
                f"{person or 'this subject'} on file — sculpt needs 3 angles "
                "or explicit single:true. Upload 2 more views (or label them "
                "via people), then sculpt once instead of three times.", 400)
        # New sculpt = one mesh credit. Order: genesis hook (first mesh
        # free, once per owner ever) → credit balance (pay once per pet) →
        # daily allowance (0 by default; promos only). Cached hits above
        # never reach here and never charge — products bind to the one mesh.
        # Funding source is stored on the mesh row so refunds restore exactly
        # what was spent (genesis→genesis, credits→ledger, daily→day usage).
        who = person or "this subject"
        genesis = db.claim_genesis_mesh(c, owner)
        funding_ref = 0
        if genesis:
            mesh_note = "genesis"
            balance = db.credit_balance(c, owner)
        else:
            balance = db.credit_balance(c, owner)
            if balance > 0:
                before = balance
                balance = db.grant_credits(c, owner, -1, f"mesh:{photo_id}")
                mesh_note = "credits"
                # ledger row id for refund-by-source
                r = c.execute("SELECT id FROM credit_ledger WHERE owner=? AND reason=?"
                              " ORDER BY id DESC LIMIT 1", (owner, f"mesh:{photo_id}")).fetchone()
                funding_ref = int(dict(r)["id"]) if r else 0
                _ = before
            else:
                ok, used = db.spend_credit(c, owner, day, "mesh", config.FREE_DAILY["mesh"])
                if not ok:
                    top = credit_top_up(owner, c)
                    raise PipelineError(
                        f"Your free first mesh is used — top up OddHobb credits "
                        f"to sculpt {who} (earn +1 per paid order). Meshes you "
                        f"already own stay free forever.",
                        402,
                        data=top,
                    )
                mesh_note = "daily"
                balance = db.credit_balance(c, owner)

        mid = db.create_mesh(c, photo_id, funding=mesh_note, funding_ref=funding_ref)
        db.enqueue(c, "mesh.generate", mid,
                   {"multi": angles[:4] if multi else []})
        mesh = db.get_mesh(c, mid)
        out = db.dump(mesh)
        out["credits_remaining"] = balance
        out["mesh_funding"] = mesh_note
        out["angles"] = len(angles) if multi else 1
        out["multi_image"] = multi
    return {"mesh": out, "reused": False}


def _mesh_route() -> tuple[str, int]:
    """(provider_name, marginal_cost_cents). Trellis first when a host is
    configured; Meshy otherwise. tripo never auto-routes (paid)."""
    import os
    if os.environ.get("TRELLIS_ENDPOINT", "").strip():
        return "trellis.selfhost", 0
    return "local.meshy", 0


def _run_trellis_attempt(c, mid: str, src: Path, job_id: str) -> bool:
    """Try the self-hosted trellis adapter. True = accepted with a usable
    GLB (persisted + activated + job done). False = fall back to Meshy.

    QC-fail triggers fallback: adapter exception, or a result with no
    downloadable GLB URL. Nothing here hangs a job — Meshy always follows.
    """
    try:
        from backend.creative.providers import router as _router
        from backend.creative.providers.base import ProviderNotConfigured as _PNC
    except Exception:
        return False
    try:
        ad = _router.resolve_policy("mesh", policy="specific",
                                    route="trellis.selfhost", keychain=None)
    except Exception:
        return False
    try:
        photo_url = meshy._data_uri(src)
        res = ad.run({"photo_url": photo_url, "single": True})
    except Exception as e:  # noqa: BLE001 — any trellis failure → Meshy
        db.update_mesh(c, mid, error=f"trellis attempt failed, Meshy fallback: {e}"[:400])
        return False
    # find a usable GLB URL in whatever shape the endpoint returns
    glb_url = ""
    if isinstance(res, dict):
        glb_url = str(res.get("glb_url") or res.get("model_url") or "")
        inner = res.get("result")
        if not glb_url and isinstance(inner, dict):
            glb_url = str(inner.get("glb_url") or inner.get("model_url") or "")
    if not glb_url:
        db.update_mesh(c, mid,
                       error="trellis returned no usable GLB, Meshy fallback")
        return False
    try:
        keys = _persist_artifacts(c, mid, {"glb": glb_url})
    except Exception as e:  # noqa: BLE001 — download/persist failed → Meshy
        db.update_mesh(c, mid, error=f"trellis artifact persist failed: {e}"[:400])
        return False
    _activate(c, mid, keys)
    db.update_mesh(c, mid, provider="trellis.selfhost")
    db.finish_job(c, job_id, "done")
    return True


def run_generate(job_id: str) -> None:
    """mesh.generate — trellis first when configured, else Meshy (or stub)."""
    with db.connect() as c:
        mid = _subject_of(c, job_id)
        mesh = db.get_mesh(c, mid)
        if mesh is None:
            db.finish_job(c, job_id, "failed", "mesh row vanished")
            return
        photo = db.get_photo(c, mesh["photo_id"])
        if photo is None:
            db.update_mesh(c, mid, status="failed", error="source photo missing")
            db.finish_job(c, job_id, "failed", "source photo missing")
            return

        try:
            src = _local_photo(dict(photo))
        except PipelineError as e:
            db.update_mesh(c, mid, status="failed", error=str(e))
            db.finish_job(c, job_id, "failed", str(e))
            return

        if meshy.is_stub():
            _complete_stub(c, mid, src)
            db.finish_job(c, job_id, "done")
            return

        # Route: self-hosted trellis first when a host is configured ($0
        # marginal), Meshy on trellis failure or QC fail. fal.tripo stays a
        # manual fallback (paid, needs approval) — never auto-routed.
        route, route_cost = _mesh_route()
        db.update_mesh(c, mid, route=route, route_cost_cents=route_cost)
        if route == "trellis.selfhost":
            if _run_trellis_attempt(c, mid, src, job_id):
                return
            # fell through: trellis failed or no usable artifact → Meshy

        try:
            payload = _job_payload(c, job_id)
            pids = [p for p in (payload.get("multi") or []) if p != mesh["photo_id"]]
            if pids:
                urls = [meshy._data_uri(src)]
                for pid in pids[:3]:
                    p = db.get_photo(c, pid)
                    if p:
                        urls.append(meshy._data_uri(_local_photo(dict(p))))
                task_id = meshy.create_multi_image_build(urls[:4]) if len(urls) >= 2 \
                    else meshy.create_task(src)
            else:
                task_id = meshy.create_task(src)
        except meshy.MeshyError as e:
            db.update_mesh(c, mid, status="failed", error=str(e)[:400])
            db.finish_job(c, job_id, "failed", str(e)[:400])
            _refund_mesh(mid)
            return

        db.update_mesh(c, mid, status="running", provider_task=task_id, stub=0)
        db.enqueue(c, "mesh.poll", mid)
        db.finish_job(c, job_id, "done")


def run_poll(job_id: str) -> None:
    """mesh.poll — one poll against Meshy; re-queues itself until settled."""
    with db.connect() as c:
        mid = _subject_of(c, job_id)
        mesh = db.get_mesh(c, mid)
        if mesh is None or not mesh["provider_task"]:
            db.finish_job(c, job_id, "failed", "no provider task")
            return
        payload = _job_payload(c, job_id)
        getter = meshy.get_multi_task if payload.get("multi") else meshy.get_task
        try:
            raw = getter(mesh["provider_task"])
        except meshy.MeshyError as e:
            db.finish_job(c, job_id, "failed", str(e)[:400])
            db.enqueue(c, "mesh.poll", mid)   # transient: try again
            return

        status, err = meshy.normalise_status(raw)
        if status == "failed":
            db.update_mesh(c, mid, status="failed", error=err)
            db.finish_job(c, job_id, "failed", err)
            _refund_mesh(mid)   # provider failed: credit back
            return

        if status != "succeeded":
            db.update_mesh(c, mid, status=status)
            db.finish_job(c, job_id, "done")
            time.sleep(1)
            db.enqueue(c, "mesh.poll", mid)
            return

        art = meshy.extract_artifacts(raw)
        try:
            keys = _persist_artifacts(c, mid, art)
        except Exception as e:
            db.finish_job(c, job_id, "failed", str(e)[:400])
            db.enqueue(c, "mesh.poll", mid)
            return

        _activate(c, mid, keys)
        db.finish_job(c, job_id, "done")


# ── helpers ───────────────────────────────────────────────────────────

def _subject_of(c, job_id: str) -> str:
    row = c.execute("SELECT subject_id FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        raise PipelineError("job not found", 404)
    return row["subject_id"]


def _owner_of(c, mid: str) -> str:
    """mesh → photo → owner. Storage keys are namespaced per account."""
    row = c.execute(
        "SELECT p.owner FROM meshes m JOIN photos p ON p.id=m.photo_id WHERE m.id=?",
        (mid,),
    ).fetchone()
    return (row["owner"] if row else "") or "anon"


def _complete_stub(c, mid: str, src: Path) -> None:
    """No Meshy key: synthesize the mesh so the rest of the system is real."""
    res = meshy.stub_result()
    keys = storage.mesh_keys(_owner_of(c, mid), mid)
    config.ensure_dirs()
    stage = config.LOCAL_MESH / mid
    stage.mkdir(parents=True, exist_ok=True)
    glb = stage / "model.glb"
    glb.write_bytes(res.glb_bytes or b"")
    storage.put(glb, keys["glb"])
    _activate(c, mid, {"glb": keys["glb"], "thumbnails": [], "textures": []}, stub=True)


def _persist_artifacts(c, mid: str, art: dict) -> dict:
    """Download Meshy results immediately (their URLs expire) then push to R2."""
    keys = storage.mesh_keys(_owner_of(c, mid), mid)
    stage = config.LOCAL_MESH / mid
    stage.mkdir(parents=True, exist_ok=True)
    out: dict = {"glb": "", "thumbnails": [], "textures": []}

    if art.get("glb"):
        local = stage / "model.glb"
        _download(art["glb"], local)
        storage.put(local, keys["glb"])
        out["glb"] = keys["glb"]

    for i, url in enumerate(art.get("thumbnails", [])[:4]):
        local = stage / f"thumb_{i}.png"
        try:
            _download(url, local)
            key = f"{keys['thumbnails']}/{i}.png"
            storage.put(local, key)
            out["thumbnails"].append(key)
        except Exception:
            continue

    for i, url in enumerate(art.get("textures", [])[:6]):
        local = stage / f"texture_{i}.png"
        try:
            _download(url, local)
            key = f"{keys['textures']}/{i}.png"
            storage.put(local, key)
            out["textures"].append(key)
        except Exception:
            continue

    if not out["glb"]:
        raise PipelineError("Meshy returned no GLB")
    return out


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "figgsite/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        dest.write_bytes(r.read())


def _activate(c, mid: str, keys: dict, stub: bool = False) -> None:
    """Write the mesh down and bind it across the product line."""
    db.update_mesh(
        c, mid,
        status="succeeded",
        error="",
        glb_key=keys.get("glb", ""),
        thumb_keys=json.dumps(keys.get("thumbnails", [])),
        texture_keys=json.dumps(keys.get("textures", [])),
        print_ready=1,
        stub=1 if stub else 0,
    )
    db.bind_products(c, mid, config.PRODUCTS.keys())


def run_all(max_jobs: int = 20) -> int:
    """Drain queued work. Called by the worker loop and by tests."""
    done = 0
    handlers = {"mesh.generate": run_generate, "mesh.poll": run_poll}
    for _ in range(max_jobs):
        progressed = False
        for kind, fn in handlers.items():
            with db.connect() as c:
                job = db.claim_job(c, kind)
                if job is None:
                    continue
                jid = job["id"]
            progressed = True
            done += 1
            try:
                fn(jid)
            except Exception as e:  # never let one job kill the loop
                with db.connect() as c:
                    db.finish_job(c, jid, "failed", str(e)[:400])
        if not progressed:
            break
    return done
