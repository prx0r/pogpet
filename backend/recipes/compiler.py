"""Compiler: person x recipe -> finished product (card actual.md).

The ONLY canonical path from a recommendation to a buyable card. It binds
a subject (photos, profile facts) to a published recipe (eligibility,
inputs, generation slots, renderer layout), saves an immutable revision,
and enqueues renders. Renderers, validators, storage, and checkout are the
existing backend.cards machinery — the compiler adds no second universe.
"""
from __future__ import annotations

import time
import uuid

from backend import cards as _cards
from backend import db as _db

from . import matcher as _matcher
from . import registry as _registry


def compile_wrap(owner: str, recipe_id: str, *, subject: dict,
                 motif_path: str = "", mode: str = "classic",
                 bg: tuple = (18, 56, 45),
                 sku: str = "WRAP-1-50X70",
                 generation_policy: str = "free",
                 via: str = "mcp") -> dict:
    """Internal wrap path: subject -> recipe -> transform motif -> repeat
    renderer -> sheet preview + print master. motif_path injects a finished
    motif (tests, or a reused transformed asset); empty means run the
    recipe's transform under generation_policy (free default, subsidized
    for P0-funded runs, use-mine/best with keys). Transform motifs must be
    qc-passed — injected author motifs bypass the gate. Recipes may be
    drafts here: this path, not the gallery shelf, owns wrap.
    Returns ok/manifest (local files + manifest) or ok False. Never raises."""
    from backend.renderers import wrap as _wrap
    owner = (owner or "anon").strip()[:80] or "anon"
    all_recipes = _registry.load_all()
    recipe = all_recipes.get(recipe_id, {})
    if not recipe or recipe.get("status") not in ("draft", "published"):
        return {"ok": False, "error": f"unknown or retired recipe {recipe_id}"}
    if (recipe.get("product") or {}).get("type") != "wrapping_paper":
        return {"ok": False, "error": f"{recipe_id} is not a wrapping recipe"}
    sub = subject or {}
    if not sub.get("id"):
        return {"ok": False, "error": "unknown subject — check oddhobb_people first"}
    try:
        pool = _photo_pool(owner, sub["id"])
    except Exception:
        pool = []
    need = int(((recipe.get("inputs") or {}).get("photos") or {}).get("count", 1))
    if len(pool) < need:
        return {"ok": False, "error": f"need {need} photos — only {len(pool)} confirmed"}
    motif_src, motif_prov = (motif_path or "").strip(), {"source": "injected"}
    if not motif_src:
        gen = (recipe.get("generation") or {}).get("motif") or {}
        tid = str(gen.get("transform_id") or "")
        if not tid:
            return {"ok": False, "error": "recipe names no motif transform"}
        from backend.creative import transform as _T
        tres = _T.transform(tid, pool[:3], owner=owner, policy=generation_policy,
                            subject_id=sub["id"])
        if not tres.get("ok"):
            err = str(tres.get("error") or "")
            if tres.get("status") == "running":
                return {"ok": False, "status": "running",
                        "transform_job_id": tres.get("transform_job_id"),
                        "hint": "motif still generating — poll transform_resume, then re-run compile_wrap with the reused asset"}
            return {"ok": False, "error": f"motif transform failed: {err}"}
        if tres.get("qc_status") != "passed":
            return {"ok": False, "error": "motif transform is not QC-passed yet"}
        motif_src = str((tres.get("artifact") or {}).get("url") or "")
        motif_prov = {"source": "transform", **tres.get("provenance", {})}
        if not motif_src:
            return {"ok": False, "error": "motif transform returned no usable artifact"}
    try:
        sheet = _wrap.render_sheet(motif_src, sku=sku, mode=mode, bg=tuple(bg))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"repeat renderer failed: {e}"}
    wid = "wrap_" + uuid.uuid4().hex[:12]
    base = f"owners/{_cards.storage._slug(owner)}/wrap/{wid}"
    manifest = {
        "id": wid, "owner": owner, "recipe_id": recipe["id"],
        "recipe_version": recipe.get("version", 1),
        "subject_id": sub["id"], "subject_name": sub.get("name", ""),
        "sku": sku, "sheet_px": list(sheet.size), "mode": mode,
        "bg": list(tuple(bg)), "motif": motif_prov,
        "price_cents": int((recipe.get("product") or {}).get("price_cents", 1499)),
        "via": via, "created_at": time.time(),
        "sheet": base + "/sheet.png", "preview": base + "/preview.png",
    }
    try:
        dest = _cards.cached(manifest["sheet"])
        sheet.save(dest, "PNG", optimize=True)
        prev = _wrap.sheet_preview(sheet)
        ppath = _cards.cached(manifest["preview"])
        prev.save(ppath, "PNG", optimize=True)
        manifest["local_sheet"] = str(dest)
        manifest["local_preview"] = str(ppath)
        try:
            _cards.storage.put(dest, manifest["sheet"])
            _cards.storage.put(ppath, manifest["preview"])
            manifest["stored"] = True
        except Exception:  # noqa: BLE001 — R2 optional offline
            manifest["stored"] = False
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"could not write sheet: {e}"}
    return {"ok": True, "wrap": manifest,
            "sheet_hash": _wrap.sheet_hash(sheet)}

OCCASION_TITLES = {
    "birthday": "Happy Birthday",
    "christmas": "Merry Christmas",
    "general": "Hello",
}


def build_brief(*, subject: dict, occasion: str = "birthday",
                vibe: str = "", photo_count: int = 0) -> dict:
    sub = subject or {}
    return {
        "occasion": str(occasion or "general").lower(),
        "vibe": str(vibe or ""),
        "subject_kind": "person",
        "photo_count": int(photo_count or 0),
        "recipient": {
            "subject_id": sub.get("id", ""),
            "name": sub.get("name", ""),
            "relationship": sub.get("relationship", ""),
            "interests": sub.get("interests", []),
            "memories": sub.get("memories", []),
        },
    }


def _photo_pool(owner: str, subject_id: str) -> list[str]:
    from backend import subject_assets as _sa
    res = _sa.resolve(subject_id, owner)
    ranked = sorted((res.get("body_candidates") or []) + (res.get("face_candidates") or []),
                    key=lambda c: float(c.get("quality", c.get("face_quality", 0))),
                    reverse=True)
    seen: set[str] = set()
    pids = []
    for c in ranked:
        aid = str(c.get("asset_id") or "")
        if aid and aid not in seen:
            seen.add(aid)
            pids.append(aid)
    return _cards.solo_first(owner, pids)


def _write_copy(profile: dict, tone: str, hint: str) -> tuple[str, str]:
    """(message, source). Hint first, server model when keyed, flagged fallback."""
    if (hint or "").strip():
        return hint.strip()[:240], "caller-hint"
    llm_line = _cards.generate_copy_llm(profile, tone)
    if llm_line:
        return llm_line[:240], "server-llm"
    lines = _cards.message_lines(profile, tone)
    return ((lines[0]["text"][:240] if lines else ""), "template-fallback")


def _attempt_title_art(headline: str, vibe: str, owner: str, design_id: str):
    """Inline generative title with the render contract. (key|None, note)."""
    import os as _os
    if not _os.environ.get("FAL_KEY"):
        return None, "serif-fallback"
    try:
        from backend.card_scenes import title_prompt, TITLE_VIBES
        from backend.creative.providers import fal as _fal
        v = vibe if vibe in TITLE_VIBES else "playful_balloons"
        rid = _fal._submit("fal-ai/flux/dev",
                           {"prompt": title_prompt(headline, v),
                            "image_size": "landscape_4_3", "num_images": 1},
                           _os.environ["FAL_KEY"])
        res = _fal._result("fal-ai/flux/dev", rid, _os.environ["FAL_KEY"],
                           timeout_s=120)
        imgs = ((res.get("response") or res).get("images") or [])
        if not imgs:
            return None, "generate-empty"
        import urllib.request as _url
        from pathlib import Path as _P
        from PIL import Image as _I
        tmp, _ = _url.urlretrieve(imgs[0]["url"])
        try:
            fitted = _cards.fit_title_art(_I.open(_P(tmp)))
        finally:
            _P(tmp).unlink(missing_ok=True)
        if fitted is None:
            return None, "contract-reject"
        _fal.log_spend(owner=owner, adapter="fal.title_art",
                       endpoint="fal-ai/flux/dev", est_cost_usd=0.025,
                       request_id=rid)
        key = f"owners/{_cards.storage._slug(owner)}/cards/{design_id}/title-art.png"
        dest = _cards.cached(key)
        fitted.save(dest, "PNG")
        _cards.storage.put(dest, key)
        return key, "generated"
    except Exception:
        return None, "generate-failed"


def compile(owner: str, recipe_id: str, *, subject: dict,
            occasion: str = "birthday", vibe: str = "", tone: str = "funny",
            message_hint: str = "", signature: str = "",
            variation: int = 0, title_art: bool = True,
            via: str = "mcp") -> dict:
    """Compile one finished product. Returns ok/design/proof_url/jobs/notes
    or ok False with error. Never raises on bad input."""
    owner = (owner or "anon").strip()[:80] or "anon"
    recipe = _registry.get(recipe_id)
    if not recipe:
        return {"ok": False, "error": f"unknown or retired recipe {recipe_id}"}
    sub = subject or {}
    if not sub.get("id"):
        return {"ok": False, "error": "unknown subject — check oddhobb_people first"}
    unsigned = not (signature or "").strip()
    signature = (signature or "").strip()[:40]
    try:
        pool = _photo_pool(owner, sub["id"])
    except Exception:
        pool = []
    need = int(((recipe.get("inputs") or {}).get("photos") or {}).get("count", 4))
    if len(pool) < need:
        return {"ok": False, "error": f"need {need} photos — only {len(pool)} confirmed"}
    if variation:
        pool = pool[variation:] + pool[:variation]
    pids = pool[:need]
    brief = build_brief(subject=sub, occasion=occasion, vibe=vibe,
                        photo_count=len(pool))
    if _matcher.eligible(recipe, brief):
        return {"ok": False,
                "error": "; ".join(_matcher.eligible(recipe, brief))}
    label = _cards.display_label(sub.get("name", ""), sub.get("relationship", ""))
    prof = {"name": sub.get("name", ""), "relationship": sub.get("relationship", ""),
            "interests": sub.get("interests", []), "memories": sub.get("memories", [])}
    copy_block = recipe.get("copy") or {}
    interest = (prof.get("interests") or [""])[0]
    fmt = {"label": label, "name": sub.get("name", ""),
           "interest": interest,
           "occasion_title": OCCASION_TITLES.get(str(occasion).lower(), "Hello")}
    headline_tpl = str(copy_block.get("headline") or "")
    if headline_tpl:
        try:
            title = headline_tpl.format(**fmt)[:40]
        except (KeyError, ValueError):
            base = OCCASION_TITLES.get(str(occasion).lower(), "Hello")
            title = f"{base}, {label}!"[:40]
        copy_source = "recipe-copy"
        inside_pool = copy_block.get("inside") or []
        if isinstance(inside_pool, list) and inside_pool and not (message_hint or "").strip():
            try:
                message = str(inside_pool[variation % len(inside_pool)]).format(**fmt)[:240]
            except (KeyError, ValueError):
                message, copy_source = _write_copy(prof, tone, message_hint)
            else:
                copy_source = "recipe-copy"
        else:
            message, _src2 = _write_copy(prof, tone, message_hint)
            if _src2 != "caller-hint":
                copy_source = "recipe-copy"
    else:
        base = OCCASION_TITLES.get(str(occasion).lower(), "Hello")
        title = f"{base}, {label}!"[:40]
        message, copy_source = _write_copy(prof, tone, message_hint)
    title_vibe = str(((recipe.get("typography") or {}).get("vibe"))
                      or copy_block.get("title_vibe") or "playful_balloons")
    warnings: list[str] = []
    if unsigned:
        # Previews may go unsigned — the signer is asked once, at buy time.
        warnings.append("unsigned: ask who signs before buy")
    tpl = ((recipe.get("renderer") or {}).get("template")) or "birthday_4photo"
    spec = {"template": tpl, "format": "5x7",
            "photos": [{"photo_id": pid, "crop": [0, 0, 1, 1],
                        "focus": [0.5, 0.5], "cutout": ""} for pid in pids],
            "headline": title, "recipient": sub.get("name", ""), "sender": signature,
            "inside_message": message, "title_vibe": title_vibe,
            "recipe_id": recipe["id"], "recipe_version": recipe.get("version", 1)}
    jobs = []
    title_note = "serif-fallback"
    try:
        fspec = _cards.validate(owner, spec)
    except _cards.CardError as e:
        return {"ok": False, "error": str(e)}
    did = "card_" + uuid.uuid4().hex
    t = time.time()
    with _db.connect() as c:
        c.execute("INSERT INTO card_designs (id,owner,latest,created_at,updated_at,storage_owner,via) VALUES (?,?,?,?,?,?,?)",
                  (did, owner, 1, t, t, owner, via))
        c.execute("INSERT INTO card_revisions VALUES (?,?,?,?)",
                  (did, 1, _cards.json_dump(fspec), t))
        c.commit()
    tkey, title_note = (None, "skipped")
    if title_art:
        tkey, title_note = _attempt_title_art(title, title_vibe, owner, did)
    rev = 1
    if tkey:
        try:
            fspec2 = _cards.validate(owner, {**fspec, "title_art_key": tkey})
            with _db.connect() as c:
                c.execute("INSERT INTO card_revisions VALUES (?,?,?,?)",
                          (did, 2, _cards.json_dump(fspec2), time.time()))
                c.execute("UPDATE card_designs SET latest=?,updated_at=? WHERE id=?",
                          (2, time.time(), did))
                c.commit()
            rev = 2
            fspec = fspec2
        except _cards.CardError as e:
            warnings.append(f"title art kept out: {e}")
    for kind in ("preview", "spread", "export"):
        for attempt in range(4):
            try:
                jobs.append(_cards.job_payload(_cards.enqueue(owner, did, rev, kind)))
                break
            except _cards.CardError as e:
                # burst contention: wait out the queue rather than shipping
                # a card whose buy path 409s for a missing render
                if "busy" not in str(e).lower() or attempt == 3:
                    warnings.append(f"{kind} not queued: {e}")
                    break
                time.sleep(3 + attempt * 3)
    return {"ok": True, "design": _cards.record(owner, did, rev),
            "recipe_id": recipe["id"], "recipe_version": recipe.get("version", 1),
            "copy_source": copy_source, "title_art": title_note,
            "warnings": warnings, "jobs": jobs,
            "card_url": _cards.card_url_for(did, rev),
            "proof_url": _cards.proof_url_for(did),
            "product": _cards.card_price()}
