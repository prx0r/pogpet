"""transform(): capability + references + instruction + contract.

Callers name a published transform id and hand over reference assets.
The instruction template compiles from the canonical prompt file
(prompts/<prompt_id>.md); the capability router picks today's adapter.
Outputs normalize to ready(artifact) / running(job_id) / failed(error) —
provider raw shapes never escape, and pretend-success (ok without an
artifact or job) is a failure.

Completed assets persist in transformed_assets keyed by cache hash over
(transform, version, references, overrides): generate once, reuse across
recipes. Mechanical QC gates entry into the store; failed outputs never
reach print recipes.
"""
from __future__ import annotations

import hashlib
import json

from . import transforms as _reg
from .providers import router as _router
from .providers.base import ProviderNotConfigured

# Import for side effect: adapters self-register on import. No network.
from .providers import alibaba as _ali  # noqa: F401
from .providers import fal as _fal  # noqa: F401
from .providers import higgsfield as _hf  # noqa: F401
from .providers import local as _local  # noqa: F401
from .providers import mesh as _mesh  # noqa: F401
from .providers import meta as _meta  # noqa: F401


class TransformError(Exception):
    pass


def instruction_for(t: dict) -> tuple[str, str]:
    """(template, source). Canonical = prompts/<prompt_id>.md ## prompt
    section; inline JSON template is the fallback. Missing prompt file
    with a prompt_id set is a hard error, never silent drift."""
    pid = str(t.get("prompt_id") or "").strip()
    if pid:
        from pathlib import Path as _P
        pf = _P(__file__).resolve().parents[2] / "prompts" / (pid + ".md")
        if not pf.is_file():
            raise TransformError(f"prompt {pid} has no file in prompts/")
        lines, in_prompt = [], False
        for line in pf.read_text().splitlines():
            if line.startswith("## "):
                in_prompt = line.strip().lower() == "## prompt"
                continue
            if in_prompt:
                s = line.strip()
                if s.startswith(">"):
                    lines.append(s[1:].strip())
                elif s:
                    lines.append(s)
        text = " ".join(lines).strip()
        if not text:
            raise TransformError(f"prompt {pid} has an empty ## prompt section")
        return text, f"prompts/{pid}"
    inline = ((t.get("instruction") or {}).get("template") or "").strip()
    if not inline:
        raise TransformError("transform has no instruction template")
    return inline, "inline"


def cache_key_for(transform_id: str, version: int, references: list,
                  instruction_override: str = "") -> str:
    canon = json.dumps({"t": transform_id, "v": version,
                        "refs": sorted(str(r) for r in references),
                        "ovr": instruction_override or ""},
                       sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(canon.encode()).hexdigest()[:16]


def normalize_output(out: dict, adapter_name: str) -> dict:
    """Provider shapes -> ready / running / failed. No pretend success:
    ok without an artifact or a job id is a failure."""
    out = dict(out or {})
    art = out.get("artifact")
    if isinstance(art, dict) and (art.get("url") or art.get("key") or art.get("id")):
        return {"status": "ready", "artifact": art, "adapter": adapter_name}
    for k in ("image_url", "url"):
        if isinstance(out.get(k), str) and out[k]:
            return {"status": "ready",
                    "artifact": {"url": out[k]}, "adapter": adapter_name}
    for k in ("job_id", "request_id", "task"):
        if out.get(k):
            return {"status": "running", "job_id": out[k],
                    "adapter": adapter_name, "raw": out.get(k)}
    return {"status": "failed", "adapter": adapter_name,
            "error": str(out.get("error") or "adapter produced no artifact")}


def mechanical_qc(image_bytes: bytes, t: dict) -> tuple[bool, dict, str]:
    """Minimum gate: decodes, mime, dims, aspect, alpha, size sane.
    Returns (passed, facts, reason). Never raises."""
    try:
        from PIL import Image as _I
        import io as _io
        im = _I.open(_io.BytesIO(image_bytes))
        im.load()
        w, h = im.size
    except Exception as e:  # noqa: BLE001
        return False, {}, f"undecodable image: {e}"
    if w < 256 or h < 256:
        return False, {"width": w, "height": h}, "too small (<256px)"
    if len(image_bytes) < 1024:
        return False, {"width": w, "height": h}, "suspiciously tiny file"
    facts: dict = {"width": w, "height": h, "mode": im.mode,
                   "bytes": len(image_bytes)}
    out = (t.get("output") or {})
    ar = str(out.get("aspect_ratio") or "")
    if ar not in ("", "source", "as-directed"):
        try:
            num, den = ar.split(":")
            want = float(num) / float(den)
            got = w / h
            if abs(got - want) / want > 0.05:
                return False, facts, f"aspect {got:.2f} != {ar}"
        except (ValueError, ZeroDivisionError):
            pass
    if out.get("background") == "transparent" and "A" not in im.getbands():
        return False, facts, "transparent background required, no alpha"
    return True, facts, ""


def _load_image_bytes(artifact: dict) -> bytes | None:
    """Fetch artifact bytes from a local path or http(s) URL. None when
    unavailable — the asset stays qc-pending, never passed."""
    url = str(artifact.get("url") or artifact.get("key") or "")
    if not url:
        return None
    try:
        if url.startswith(("http://", "https://")):
            import urllib.request as _url
            req = _url.Request(url, headers={"User-Agent": "Mozilla/5.0 (oddhobb-qc)"})
            with _url.urlopen(req, timeout=120) as r:
                blob = r.read(25 * 1024 * 1024 + 1)
            return blob if len(blob) <= 25 * 1024 * 1024 else None
        from pathlib import Path as _P
        p = _P(url)
        return p.read_bytes() if p.is_file() else None
    except Exception:  # noqa: BLE001
        return None


def transform(transform_id: str, references: list | None = None, *,
              owner: str = "anon", policy: str = "free",
              route: str = "", keychain: dict | None = None,
              instruction_override: str = "",
              subject_id: str = "") -> dict:
    """Run one published transform. Cache-first: same subject + transform +
    refs reuses the passed asset without spending again. Returns ok/artifact
    (+ job_id when running) or ok False. Never raises on bad input."""
    from backend import db as _db
    owner = (owner or "anon").strip()[:80] or "anon"
    t = _reg.get(transform_id)
    if not t:
        return {"ok": False, "error": f"unknown or retired transform {transform_id}"}
    refs = list(references or [])
    need = int((t.get("references") or {}).get("min_images", 0))
    if len(refs) < need:
        return {"ok": False,
                "error": f"{transform_id} needs {need} reference image(s), got {len(refs)}"}
    try:
        instruction, prompt_source = instruction_for(t)
    except TransformError as e:
        return {"ok": False, "error": str(e)}
    if instruction_override.strip():
        instruction = instruction_override.strip()[:2000]
        prompt_source = "caller-override"
    key = cache_key_for(t["id"], int(t.get("version", 1)), refs,
                        instruction_override.strip())
    with _db.connect() as c:
        try:
            hit = c.execute("SELECT * FROM transformed_assets WHERE owner=? AND cache_key=? AND qc_status='passed' ORDER BY created_at DESC LIMIT 1",
                            (owner, key)).fetchone()
        except Exception:  # noqa: BLE001 — table missing on old DBs
            hit = None
    if hit:
        h = dict(hit)
        return {"ok": True, "reused": True,
                "artifact": {"id": h["id"], "url": h["artifact_key"],
                             "width": h["width"], "height": h["height"],
                             "mime": h["mime"]},
                "provenance": {"transform_id": t["id"],
                               "transform_version": t.get("version", 1),
                               "capability": t.get("capability", ""),
                               "references_used": len(refs)}}
    capability = t.get("capability", "")
    payload = {
        "images": refs,
        "prompt": instruction,
        "preserve": t.get("preserve", []),
        "output": t.get("output", {}),
        "qc": t.get("qc", {}),
        "transform_id": t["id"],
        "transform_version": t.get("version", 1),
    }
    try:
        if policy != "free" or route:
            raw = _router.run(capability, payload, policy=policy,
                              route=route, keychain=keychain)
        else:
            raw = _router.run_for_owner(capability, owner, payload,
                                        policy=policy, route=route)
    except ProviderNotConfigured as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001 — adapter failure is data
        return {"ok": False, "error": f"{capability} failed: {e}"}
    adapter_name = str(raw.get("adapter") or "")
    norm = normalize_output(raw, adapter_name)
    if norm["status"] != "ready":
        return {"ok": False, **{k: v for k, v in norm.items() if k != "status"},
                "status": norm["status"]}
    artifact = norm["artifact"]
    blob = _load_image_bytes(artifact)
    if blob is None:
        qc_status, facts = "pending", {}
    else:
        passed, facts, reason = mechanical_qc(blob, t)
        qc_status = "passed" if passed else "failed"
        if not passed:
            return {"ok": False, "error": f"QC rejected: {reason}",
                    "facts": facts, "adapter": adapter_name}
    import time as _time
    import uuid as _uuid
    aid = "ta_" + _uuid.uuid4().hex[:16]
    asset = {"id": aid,
             "url": artifact.get("url") or artifact.get("key") or "",
             "width": facts.get("width", 0), "height": facts.get("height", 0),
             "mime": ("image/png" if str(artifact.get("url") or "").lower().endswith(".png") else "")}
    with _db.connect() as c:
        try:
            c.execute("INSERT INTO transformed_assets (id,owner,subject_id,transform_id,transform_version,reference_hashes,cache_key,artifact_key,width,height,mime,provider,provider_ref,qc_status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (aid, owner, (subject_id or "")[:80], t["id"], int(t.get("version", 1)),
                       json.dumps(refs)[:2000], key, asset["url"][:500],
                       asset["width"], asset["height"], asset["mime"],
                       adapter_name.split(".")[0] if adapter_name else "",
                       str(raw.get("request_id") or raw.get("job_id") or "")[:120],
                       qc_status, _time.time()))
            c.commit()
        except Exception:  # noqa: BLE001 — table missing on old DBs
            pass
    return {"ok": True, "reused": False, "artifact": asset,
            "qc_status": qc_status,
            "provenance": {"transform_id": t["id"],
                           "transform_version": t.get("version", 1),
                           "capability": capability,
                           "references_used": len(refs),
                           "prompt_source": prompt_source}}


def describe(transform_id: str) -> dict:
    """The transform card: what it needs, what it makes. No execution."""
    t = _reg.get(transform_id)
    if not t:
        return {"ok": False, "error": f"unknown or retired transform {transform_id}"}
    return {"ok": True, "transform": {k: t[k] for k in
            ("id", "version", "capability", "references", "preserve",
             "output", "qc", "prompt_id", "products") if k in t}}
