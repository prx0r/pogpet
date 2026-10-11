"""REST for the canonical card engine (cardgen). Mounted on the cards blueprint,
so it inherits its owner resolution, key permissions and CardError handling.

  GET  /api/cardgen/status                         can this server generate? (keys/flags present, no secrets)
  GET  /api/cardgen/templates                      the roster and what each wants from photos
  POST /api/cardgen/recommend {subject_id, occasion, profile?}
       -> ready: templates these photos can make (with the photo ids cast)
       -> blocked: what each other template still needs ("needs a happy solo photo of them")
  POST /api/cardgen/make {subject_id, template_id, profile?, copy?}   -> {job_id}  (202)
  GET  /api/cardgen/jobs/<job_id>                  status, step, then design + views + price
"""
from __future__ import annotations

import os

from flask import jsonify, request


def _profile(owner: str, subject_id: str, extra: dict | None) -> dict:
    from backend import db
    prof = {}
    try:
        with db.connect() as c:
            r = c.execute("SELECT name, kind FROM studio_subjects WHERE id=? AND owner=?",
                          (subject_id, owner)).fetchone()
        if r:
            prof["name"] = r["name"]
            if r["kind"] == "pet":
                prof["kind"] = "pet"
                prof["pet_name"] = r["name"]
    except Exception:
        pass
    try:  # what /studio/subjects/<sid>/profile saved: relationship + interests
        from backend import subjects as S
        with db.connect() as c:
            S.ensure_tables(c)
            saved = S.profile_for(c, owner, subject_id) or {}
        if saved.get("relationship"):
            prof["relationship"] = saved["relationship"]
        ints = (saved.get("profile") or {}).get("interests")
        if ints:
            prof["interests"] = list(ints)
    except Exception:
        pass
    for k, v in (extra or {}).items():
        if k in ("name", "relationship", "interests", "memories", "nicknames", "tone", "occasion",
                 "recipient", "sender", "surname", "place", "prop", "pet_name") and v:
            prof[k] = v
    return prof


def attach(bp, CardError, card_price, card_url_for, proof_url_for):
    from cardgen import engine as E

    def _wrap(fn):
        try:
            return fn()
        except E.EngineError as e:
            raise CardError(str(e), e.code)

    @bp.get("/api/cardgen/templates")
    def cardgen_templates():
        from cardgen import wants as W
        return jsonify(ok=True, templates=[
            {"id": t["id"], "occasions": t["occasions"], "interests": t["interests"],
             "wants": {k: W.describe(v) for k, v in t["wants"].items()},
             "wants_spec": t["wants"]} for t in E.templates()])

    @bp.get("/api/cardgen/status")
    def cardgen_status():
        """Deployment readiness, no secrets: what generation still needs on this server."""
        import shutil
        env = lambda k: bool((os.environ.get(k) or "").strip())
        checks = {"fal_key": env("FAL_KEY"), "openrouter_key": env("OPENROUTER_API_KEY"),
                  "cardgen_live": os.environ.get("CARDGEN_LIVE") == "1",
                  "tesseract": bool(shutil.which("tesseract"))}
        need = [k for k in ("fal_key", "cardgen_live") if not checks[k]]
        ts = E.templates()
        return jsonify(ok=True, can_generate=not need, missing=need, checks=checks,
                       optional_missing=[k for k in ("openrouter_key", "tesseract") if not checks[k]],
                       templates=len(ts), pet_templates=sum(E.is_pet_template(t) for t in ts),
                       daily_cap=int(os.environ.get("CARDGEN_DAILY_CAP") or 12))

    @bp.post("/api/cardgen/recommend")
    def cardgen_recommend():
        owner = request.card_owner
        b = request.get_json() or {}
        sid = str(b.get("subject_id") or "").strip()[:80]
        if not sid:
            raise CardError("subject_id is required", 400)
        occ = str(b.get("occasion") or "birthday").strip().lower()[:20]
        prof = _profile(owner, sid, b.get("profile"))
        return _wrap(lambda: jsonify(E.recommend(owner, sid, occ, prof)))

    @bp.post("/api/cardgen/make")
    def cardgen_make():
        owner = request.card_owner
        b = request.get_json() or {}
        sid = str(b.get("subject_id") or "").strip()[:80]
        tid = str(b.get("template_id") or "").strip()[:60]
        if not (sid and tid):
            raise CardError("subject_id and template_id are required", 400)
        prof = _profile(owner, sid, b.get("profile"))
        prof.setdefault("occasion", str(b.get("occasion") or "birthday"))
        jid = _wrap(lambda: E.start(owner, sid, tid, prof, b.get("copy") or {}))
        return jsonify(ok=True, job_id=jid, status="queued",
                       poll=f"/api/cardgen/jobs/{jid}"), 202

    @bp.get("/api/cardgen/jobs/<jid>")
    def cardgen_job(jid):
        owner = request.card_owner
        j = _wrap(lambda: E.job(owner, jid))
        body = {"ok": True, "job_id": jid, "status": j["status"], "step": j["step"],
                "template_id": j["template_id"], "error": j["error"]}
        if j["status"] == "ready":
            did, rev = j["design_id"], j["revision"]
            base = f"/api/cards/{did}/r{rev}"
            body.update(design_id=did, revision=rev,
                        views={"front": f"{base}/preview", "inside": f"{base}/inside",
                               "back": f"{base}/back", "print_pdf": f"{base}/export"},
                        card_url=card_url_for(did, rev), proof_url=proof_url_for(did),
                        product=card_price(), copy=(j["record"] or {}).get("copy"),
                        photos=((j["record"] or {}).get("photos") or {}).get("roles"),
                        qa=(j["record"] or {}).get("qa"),
                        buy=f"POST /api/cards/{did}/checkout")
        return jsonify(body)
