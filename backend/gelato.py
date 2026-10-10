"""Gelato template fill (staged until a dashboard template exists).

Native fit for the labels engine: a Gelato product template carries NAMED
image placeholders; create-from-template fills each placeholder by name
with a fileUrl and Gelato renders mockups in the background. Our side maps
label slots → placeholder names (docs/provider-templates.md) and supplies
ranked face fileUrls from product_assets candidates.

Staged: works end-to-end once GELATO_STORE_ID is set and a templateId is
passed. No order endpoint here — fulfilment stays human-approved.
Docs: dashboard.gelato.com/docs/ecommerce (imported 2026-10-10).
"""
from __future__ import annotations

import json
import os
import urllib.request

BASE = "https://ecommerce.gelatoapis.com/v1"


class GelatoError(Exception):
    pass


def api_key() -> str:
    p = _env_path()
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("GELATO_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("GELATO_API_KEY", "")


def _env_path():
    from pathlib import Path
    from . import config
    return Path(config.ROOT) / ".env"


def _call(method: str, path: str, body: dict | None = None,
          timeout: int = 30) -> dict:
    key = api_key()
    if not key:
        raise GelatoError("no GELATO_API_KEY in .env")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("X-API-KEY", key)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "OddHobb/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise GelatoError(f"Gelato {e.code}: {e.read().decode()[:300]}") from None
    except Exception as e:
        raise GelatoError(f"Gelato unreachable: {e}") from None


def get_template(template_id: str) -> dict:
    """Template variants + image placeholder names (the fill contract)."""
    d = _call("GET", f"/templates/{template_id}")
    if d.get("id"):
        return {"ok": True, "template": d}
    return {"ok": False, "error": str(d)[:300]}


def fill_from_template(*, store_id: str = "", template_id: str, title: str,
                       description: str = "", tags: list | None = None,
                       variants: list | None = None,
                       visible: bool = False) -> dict:
    """Create a product from a template, filling named image placeholders.

    variants: [{templateVariantId, imagePlaceholders: [{name, fileUrl,
    fitMethod? (slice|meet)}]}]. Omit variants to inherit the template's.
    Staged (no call) until a store id + template id are supplied.
    """
    store_id = store_id or os.environ.get("GELATO_STORE_ID", "")
    if not api_key() or not store_id or not template_id:
        return {"ok": False, "staged": True,
                "error": "needs GELATO_API_KEY + store id + templateId "
                         "(build the template in the Gelato dashboard first)"}
    body = {"templateId": template_id, "title": title,
            "description": description,
            "isVisibleInTheOnlineStore": visible,
            "salesChannels": ["web"], "tags": tags or []}
    if variants:
        body["variants"] = variants
    try:
        d = _call("POST", f"/stores/{store_id}/products:create-from-template", body)
    except GelatoError as e:
        return {"ok": False, "staged": False, "error": str(e)[:300]}
    return {"ok": True, "staged": False, "product": d}
