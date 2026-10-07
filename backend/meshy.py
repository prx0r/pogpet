"""Meshy client + offline stub.

Real path (needs MESHY_API_KEY), per https://docs.meshy.ai (llms.txt):
    POST /openapi/v1/image-to-3d  -> {"result": task_id}
    GET  /openapi/v1/image-to-3d/{id} -> task object (status/model_urls/...)
Paths are lowercase and per-resource — the old generic /tasks/{id} route
is gone (NoMatchingRoute). Meshy refunds server-side on FAILED tasks;
we mirror that by refunding our free-tier sculpt on provider failure.

Meshy accepts base64 data URIs for the source image, so we never need the
photo to be publicly reachable — it goes straight from our private staging
to Meshy. When no key is configured we synthesize a valid GLB instead, so
the whole pipeline (store, bind, fan-out, agent) is testable offline and
flips to live by just setting MESHY_API_KEY.
"""
from __future__ import annotations

import base64
import json
import struct
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from . import config


class MeshyError(Exception):
    pass


class MeshyAuthError(MeshyError):
    pass


# ── HTTP ──────────────────────────────────────────────────────────────

def _req(method: str, path: str, body: dict | None = None, timeout: int = 60) -> dict:
    url = f"{config.MESHY_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {config.MESHY_API_KEY}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        payload = e.read().decode("utf-8", "replace")[:400]
        if e.code in (401, 403):
            raise MeshyAuthError(f"Meshy rejected the key ({e.code}): {payload}") from None
        raise MeshyError(f"Meshy {e.code}: {payload}") from None
    except urllib.error.URLError as e:
        raise MeshyError(f"Meshy unreachable: {e.reason}") from None


def _data_uri(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/jpeg;base64,{b64}"


# ── real ──────────────────────────────────────────────────────────────

def create_task(image_path: Path, *, chibi: bool = False) -> str:
    """Start a mesh job. `chibi` selects the Creative Lab figure track."""
    if not config.MESHY_API_KEY:
        raise MeshyAuthError("MESHY_API_KEY not set")
    uri = _data_uri(image_path)
    if chibi:
        # Creative Lab: prototype (cheap preview) then build.
        res = _req("POST", "/creative-lab/figure/v1/prototype", {"image_url": uri})
        return str(res.get("result") or res.get("task_id") or "")

    res = _req("POST", "/image-to-3d", {
        "image_url": uri,
        "ai_model": "latest",
        "should_texture": True,
        "texture_resolution": "2k",
        "target_formats": ["glb"],
        "multi_view_thumbnails": True,
    })
    tid = res.get("result") or res.get("task_id")
    if not tid:
        raise MeshyError(f"no task id in response: {json.dumps(res)[:300]}")
    return str(tid)


def get_task(task_id: str) -> dict:
    if not config.MESHY_API_KEY:
        raise MeshyAuthError("MESHY_API_KEY not set")
    return _req("GET", f"/image-to-3d/{task_id}")


def get_multi_task(task_id: str) -> dict:
    if not config.MESHY_API_KEY:
        raise MeshyAuthError("MESHY_API_KEY not set")
    return _req("GET", f"/multi-image-to-3d/{task_id}")


# ── companion path: screenshot -> multiview -> multi-image 3D ──────────
# OFF-PIPELINE: research helpers only. Meshy is GENESIS ONLY — it creates the
# mesh (single image-to-3d or multi-image-to-3d from REAL photos) and nothing
# else. View synthesis, repair and retexture never go to Meshy: angles must be
# real photos (the 3-angle gate), repair is local Blender, rendering is ours.
# backend/pipeline.py must never import the two functions below
# (tests/test_mesh_gate.py::TestGenesisOnly enforces it).

def create_multiview(image_path: Path, *, prompt: str = "") -> str:
    """Screenshot -> consistent multi-view set. Returns a task id."""
    if not config.MESHY_API_KEY:
        raise MeshyAuthError("MESHY_API_KEY not set")
    res = _req("POST", "/image-to-image", {
        "image_url": _data_uri(image_path),
        "prompt": prompt or ("preserve character exactly, neutral pose, "
                             "clean studio background, generate multiview"),
        "generate_multi_view": True,
    })
    tid = res.get("result") or res.get("task_id")
    if not tid:
        raise MeshyError(f"no task id in response: {json.dumps(res)[:300]}")
    return str(tid)


def create_multi_image_build(image_urls: list[str]) -> str:
    """1-4 views of the same subject -> textured mesh. First view is front."""
    if not config.MESHY_API_KEY:
        raise MeshyAuthError("MESHY_API_KEY not set")
    if not (1 <= len(image_urls) <= 4):
        raise MeshyError("multi-image build needs 1-4 view URLs")
    res = _req("POST", "/multi-image-to-3d", {
        "image_urls": image_urls,
        "should_texture": True,
        "target_formats": ["glb"],
    })
    tid = res.get("result") or res.get("task_id")
    if not tid:
        raise MeshyError(f"no task id in response: {json.dumps(res)[:300]}")
    return str(tid)


def repair_printability(model_url: str) -> str:
    """OFF-PIPELINE (see above): print repair is local Blender, never Meshy."""
    if not config.MESHY_API_KEY:
        raise MeshyAuthError("MESHY_API_KEY not set")
    res = _req("POST", "/repair-printability", {"model_url": model_url})
    tid = res.get("result") or res.get("task_id")
    if not tid:
        raise MeshyError(f"no task id in response: {json.dumps(res)[:300]}")
    return str(tid)


# ── status mapping ────────────────────────────────────────────────────

def normalise_status(raw: dict) -> tuple[str, str]:
    """Meshy task -> our status vocabulary. Returns (status, error)."""
    s = str(raw.get("status", "")).upper()
    if s in ("SUCCEEDED", "SUCCESS", "COMPLETED"):
        return "succeeded", ""
    if s in ("FAILED", "CANCELED", "CANCELLED"):
        return "failed", str(raw.get("error", {}).get("message", raw.get("status", "")))[:400]
    if s in ("PENDING", "QUEUED", "IN_QUEUE"):
        return "queued", ""
    return "running", ""


def extract_artifacts(raw: dict) -> dict:
    """Pull glb / thumbnails / textures out of a Meshy task payload."""
    r = raw.get("result", raw)
    urls = r.get("model_urls") or {}
    glb = urls.get("glb") or urls.get("obj") or ""
    thumbs = [u for u in (r.get("thumbnail_urls") or []) if u]
    textures = [u for u in (r.get("texture_urls") or []) if u]
    return {"glb": glb, "thumbnails": thumbs, "textures": textures}


# ── offline stub ──────────────────────────────────────────────────────

def _stub_glb() -> bytes:
    """A minimal but *valid* GLB: unit cube with POSITION + NORMAL + indices.

    Lets the viewer, the registry and the product fan-out all run without a
    Meshy key. Deterministic, so re-running doesn't churn artifacts.
    """
    corners = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
               (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
    faces = [  # (indices, normal)
        ([0, 1, 2, 3], (0, 0, -1)), ([5, 4, 7, 6], (0, 0, 1)),
        ([4, 0, 3, 7], (-1, 0, 0)), ([1, 5, 6, 2], (1, 0, 0)),
        ([3, 2, 6, 7], (0, 1, 0)), ([4, 5, 1, 0], (0, -1, 0)),
    ]
    positions: list[float] = []
    normals: list[float] = []
    indices: list[int] = []
    for quad, n in faces:
        base = len(positions) // 3
        for vi in quad:
            positions.extend(corners[vi])
            normals.extend(n)
        indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])

    pos_bytes = struct.pack(f"<{len(positions)}f", *positions)
    nrm_bytes = struct.pack(f"<{len(normals)}f", *normals)
    idx_bytes = struct.pack(f"<{len(indices)}H", *indices)
    while len(idx_bytes) % 4:
        idx_bytes += b"\x00"

    bin_blob = pos_bytes + nrm_bytes + idx_bytes
    pos_off, nrm_off, idx_off = 0, len(pos_bytes), len(pos_bytes) + len(nrm_bytes)

    gltf = {
        "asset": {"version": "2.0", "generator": "figgsite-stub"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "stub-figure"}],
        "meshes": [{"primitives": [{
            "attributes": {"POSITION": 0, "NORMAL": 1}, "indices": 2}]}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": len(positions) // 3,
             "type": "VEC3", "min": [-1, -1, -1], "max": [1, 1, 1]},
            {"bufferView": 1, "componentType": 5126, "count": len(normals) // 3,
             "type": "VEC3"},
            {"bufferView": 2, "componentType": 5123, "count": len(indices),
             "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": pos_off, "byteLength": len(pos_bytes)},
            {"buffer": 0, "byteOffset": nrm_off, "byteLength": len(nrm_bytes)},
            {"buffer": 0, "byteOffset": idx_off, "byteLength": len(idx_bytes)},
        ],
        "buffers": [{"byteLength": len(bin_blob)}],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return struct.pack("<I", len(payload)) + tag + payload

    total = 12 + 8 + len(js) + 8 + len(bin_blob)
    return (struct.pack("<III", 0x46546C67, 2, total)
            + chunk(b"JSON", js) + chunk(b"BIN\x00", bin_blob))


@dataclass
class StubResult:
    status: str = "succeeded"
    glb_bytes: bytes | None = None
    thumb_keys: list[str] = field(default_factory=list)


def stub_result() -> StubResult:
    return StubResult(glb_bytes=_stub_glb())


def is_stub() -> bool:
    return not config.MESHY_API_KEY
