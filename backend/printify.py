"""Printify blueprint fill (staged until a shop + blueprint are chosen).

Printify's unit is blueprint (catalog product) + print provider + variant +
placeholder (print area, px dims). createProduct pins our artwork URL into
each placeholder; mockups generate on their side. Our side maps label slots
→ placeholders and supplies ranked face artwork at placeholder px
(docs/provider-templates.md).

Staged: works end-to-end once PRINTIFY_SHOP_ID is set and blueprint /
provider / variant ids are passed. No order endpoint here — fulfilment
stays human-approved. Docs: developers.printify.com (imported 2026-10-10).
Rate limits apply to product + mockup calls (200/30min); batch calmly.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

BASE = "https://api.printify.com/v1"


class PrintifyError(Exception):
    pass


# Regional print providers (Printify directory, recorded 2026-10-10 —
# IDs verified live where they appear on catalog blueprints).
# Routing policy: prefer a provider in the customer's region; Choice (99)
# auto-routes when specified. IDs are stable Printify references.
PROVIDERS_BY_REGION = {
    "US": ["CatPrint", "District Photo", "Imagine Your Photos",
           "Printed Mint", "Printify Choice", "Print Geek CA"],
    "UK_EU": ["Eco Print Partner GB", "Print Clever GB", "Pixxprint DE",
              "PH Print Norden LV", "Print Pigeons LV", "X-Print DE"],
    "AU": ["Prima Printing", "The Print Bar"],
    "CN": ["Printdoors", "Smart Printee"],
}


def providers_for_region(region: str) -> list:
    """Provider names serving a region (US/UK_EU/AU/CN). Names feed
    dashboard provider choice; IDs resolve per blueprint at fill time."""
    return list(PROVIDERS_BY_REGION.get((region or "").upper(), []))


def api_token() -> str:
    p = Path(__file__).resolve().parent.parent / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("PRINTIFY_API_TOKEN="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("PRINTIFY_API_TOKEN", "")


def _call(method: str, path: str, body: dict | None = None,
          timeout: int = 30) -> dict:
    tok = api_token()
    if not tok:
        raise PrintifyError("no PRINTIFY_API_TOKEN in .env")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "OddHobb/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise PrintifyError(f"Printify {e.code}: {e.read().decode()[:300]}") from None
    except Exception as e:
        raise PrintifyError(f"Printify unreachable: {e}") from None


def upload_image(*, file_name: str, url: str = "", contents_b64: str = "") -> dict:
    """Upload artwork to the merchant media library. Returns upload id."""
    body = {"file_name": file_name}
    if url:
        body["url"] = url
    elif contents_b64:
        body["contents"] = contents_b64
    else:
        return {"ok": False, "error": "url or contents_b64 required"}
    try:
        d = _call("POST", "/uploads/images.json", body)
    except PrintifyError as e:
        return {"ok": False, "error": str(e)[:300]}
    return {"ok": True, "upload": d}


def placeholders(blueprint_id: int, print_provider_id: int) -> dict:
    """Print areas (position + px) for a blueprint+provider — the fill contract."""
    try:
        d = _call("GET", f"/catalog/blueprints/{blueprint_id}/print_providers/"
                         f"{print_provider_id}/variants.json")
    except PrintifyError as e:
        return {"ok": False, "error": str(e)[:300]}
    variants = d if isinstance(d, list) else d.get("variants", [])
    areas = {}
    for v in variants:
        for p in (v.get("placeholders") or []):
            areas.setdefault(p.get("position"), p)
    return {"ok": True, "placeholders": areas}


def create_product(*, shop_id: str = "", title: str, blueprint_id: int,
                   print_provider_id: int, variants: list,
                   print_areas: list) -> dict:
    """Pin artwork into placeholders (variant_ids + placeholders with
    src/print-area ids). Staged until a shop id is configured."""
    shop_id = shop_id or os.environ.get("PRINTIFY_SHOP_ID", "")
    if not api_token() or not shop_id:
        return {"ok": False, "staged": True,
                "error": "needs PRINTIFY_API_TOKEN + shop id "
                         "(pick blueprint/provider in the dashboard first)"}
    body = {"title": title, "blueprint_id": blueprint_id,
            "print_provider_id": print_provider_id, "variants": variants,
            "print_areas": print_areas}
    try:
        d = _call("POST", f"/shops/{shop_id}/products.json", body)
    except PrintifyError as e:
        return {"ok": False, "staged": False, "error": str(e)[:300]}
    return {"ok": True, "staged": False, "product": d}
