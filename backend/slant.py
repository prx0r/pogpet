"""Slant3D V2 direct client (key stored — upgrades the MCP hop).

Slant is a 3D-print farm backend, not a personalization engine: STL in →
estimate (free, ms) → draft order (free) → process (CHARGED) → track.
Order items: PRINT (our meshes) + COMPONENT (their hardware: magnets,
keychain findings, screws) + STATIONERY (their 4x6 custom card).
Key rules (from their integration guide): server-side only, filamentId
mandatory on estimate+order, drafts commit only after payment (webhook),
order row first (idempotent fulfilment).
Docs: docs/vendor/slant.md. Spec: slant3dapi.com/v2/api/openapi.json.
Spend gate: process() requires approve=True. Estimating is free.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

BASE = "https://slant3dapi.com/v2/api"


class SlantError(Exception):
    pass


def api_key() -> str:
    p = Path(__file__).resolve().parent.parent / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("SLANT3D_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("SLANT3D_API_KEY", "")


def _call(method: str, path: str, body: dict | None = None,
          timeout: int = 60) -> dict:
    key = api_key()
    if not key:
        raise SlantError("no SLANT3D_API_KEY in .env")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "OddHobb/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise SlantError(f"Slant {e.code}: {e.read().decode()[:300]}") from None
    except Exception as e:
        raise SlantError(f"Slant unreachable: {e}") from None


def platforms() -> dict:
    """Account platforms (need ≥1 enabled before uploads). Free."""
    try:
        return {"ok": True, **_call("GET", "/platforms")}
    except SlantError as e:
        return {"ok": False, "error": str(e)[:200]}


def filaments() -> dict:
    """Filament catalogue with publicIds (estimate/order need one). Free."""
    try:
        d = _call("GET", "/filaments")
        items = d.get("data", d) if isinstance(d, dict) else d
        return {"ok": True, "filaments": items}
    except SlantError as e:
        return {"ok": False, "error": str(e)[:200]}


def default_filament(items: list | None = None,
                     profile: str = "PLA") -> dict | None:
    """First available filament matching profile (prefer black)."""
    items = items or []
    cands = [f for f in items
             if f.get("available") and (f.get("profile") or "") == profile]
    if not cands:
        cands = [f for f in items if f.get("available")]
    for f in cands:
        if "black" in (f.get("name") or "").lower():
            return f
    return cands[0] if cands else None


def components() -> dict:
    """Hardware catalogue (magnets, findings, screws) — feeds 3D line
    hardware decisions. Free."""
    try:
        d = _call("GET", "/components")
        items = d.get("data", d) if isinstance(d, dict) else d
        return {"ok": True, "components": items}
    except SlantError as e:
        return {"ok": False, "error": str(e)[:200]}


def estimate_from_url(*, file_url: str, name: str, filament_id: str = "",
                      platform_id: str = "") -> dict:
    """Server-side URL upload → confirm → estimate. Free; needs one
    enabled platform (dashboard) when the account has none."""
    try:
        import urllib.request as _ul
        with _ul.urlopen(file_url, timeout=120) as r:
            blob = r.read()
    except Exception as e:
        return {"ok": False, "error": f"could not fetch STL: {e}"[:200]}
    if len(blob) > 250 * 1024 * 1024:
        return {"ok": False, "error": "STL over Slant 250MB limit"}
    try:
        up = _call("POST", "/files/direct-upload",
                   {"name": name, "platformId": platform_id} if platform_id
                   else {"name": name})
        presigned = (up.get("data") or up).get("presignedUrl")
        placeholder = (up.get("data") or up).get("filePlaceholder")
        if not presigned or placeholder is None:
            return {"ok": False, "error": f"no presigned URL: {str(up)[:200]}"}
        put = urllib.request.Request(presigned, data=blob, method="PUT")
        put.add_header("Content-Type", "application/octet-stream")
        with urllib.request.urlopen(put, timeout=300):
            pass
        conf = _call("POST", "/files/confirm-upload",
                     {"filePlaceholder": placeholder})
        file_id = (conf.get("data") or conf).get("publicFileServiceId")
        if not file_id:
            return {"ok": False, "error": f"no file id: {str(conf)[:200]}"}
        if not filament_id:
            fils = filaments()
            if not fils.get("ok"):
                return {"ok": False, "error": fils.get("error", "no filaments")}
            picked = default_filament(fils["filaments"])
            if not picked:
                return {"ok": False, "error": "no available filament"}
            filament_id = picked["publicId"]
        est = _call("POST", f"/files/{file_id}/estimate",
                    {"options": {"filamentId": filament_id}})
        total = (est.get("data") or est).get("total")
        return {"ok": True, "file_id": file_id, "filament_id": filament_id,
                "total_usd": total, "estimate": est}
    except SlantError as e:
        return {"ok": False, "error": str(e)[:300]}


def draft_order(*, file_id: str, filament_id: str, email: str,
                address: dict, quantity: int = 1,
                platform_id: str = "") -> dict:
    """Draft (FREE, no charge) — needs a deliverable address. Staged
    without one; process() commits only after verified payment."""
    if not (email and address):
        return {"ok": False, "staged": True,
                "error": "draft needs customer email + deliverable address"}
    body = {"customer": {"details": {"email": email, "address": address}},
            "items": [{"type": "PRINT", "quantity": max(1, quantity),
                       "publicFileServiceId": file_id,
                       "filamentId": filament_id}]}
    if platform_id:
        body["platformId"] = platform_id
    try:
        d = _call("POST", "/orders", body)
    except SlantError as e:
        return {"ok": False, "staged": False, "error": str(e)[:300]}
    order = (d.get("data") or d).get("order", {})
    if not order.get("publicId"):
        return {"ok": False, "staged": False,
                "error": f"no draft id: {str(d)[:200]}"}
    return {"ok": True, "public_id": order["publicId"],
            "printing_cost": order.get("printingCost"),
            "delivery_cost": order.get("deliveryCost"), "order": order}


def process_order(public_id: str, *, approve: bool = False) -> dict:
    """Commit a draft to production. CHARGES the card — approve + human."""
    if not approve:
        return {"ok": False, "staged": True,
                "error": "approve=True required (charges card, queues print)"}
    try:
        d = _call("POST", f"/orders/{public_id}", {"confirm": True})
    except SlantError as e:
        return {"ok": False, "staged": False, "error": str(e)[:300]}
    return {"ok": True, "result": d}
