"""Shopify fulfilment helpers — controlled custom orders.

Secrets stay in .env (SHOPIFY_STORE, SHOPIFY_API_KEY, SHOPIFY_API_SECRET,
SHOPIFY_ADMIN_TOKEN). Tokens expire ~24h via client_credentials.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API_VERSION = "2024-10"


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def store() -> str:
    return _env("SHOPIFY_STORE")


def configured() -> bool:
    return bool(store() and (
        _env("SHOPIFY_ACCESS_TOKEN") or _env("SHOPIFY_ADMIN_TOKEN")
        or (_env("SHOPIFY_API_KEY") and _env("SHOPIFY_API_SECRET"))
    ))


def _token() -> str:
    tok = _env("SHOPIFY_ACCESS_TOKEN") or _env("SHOPIFY_ADMIN_TOKEN")
    if tok:
        return tok
    cid, sec = _env("SHOPIFY_API_KEY"), _env("SHOPIFY_API_SECRET")
    if not (cid and sec):
        raise RuntimeError("Shopify credentials missing")
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": cid,
        "client_secret": sec,
    }).encode()
    req = urllib.request.Request(
        f"https://{store()}/admin/oauth/access_token",
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.loads(r.read().decode() or "{}")
    tok = payload.get("access_token")
    if not tok:
        raise RuntimeError(f"Shopify token exchange failed: {str(payload)[:200]}")
    return str(tok)


def gql(query: str, variables: dict | None = None) -> dict[str, Any]:
    if not configured():
        raise RuntimeError("Shopify not configured")
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        f"https://{store()}/admin/api/{API_VERSION}/graphql.json",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": _token(),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return {"errors": e.read().decode("utf-8", "replace")[:400]}


def shop_name() -> str | None:
    try:
        data = gql("{ shop { name myshopifyDomain } }")
        shop = (data.get("data") or {}).get("shop") or {}
        return shop.get("myshopifyDomain") or shop.get("name")
    except Exception:
        return None


def create_draft_order(line_label: str, price_cents: int, qty: int,
                       note: str = "", email: str = "") -> dict:
    """Create a Shopify draft order for a controlled custom / gift card.

    Does not charge. Merchant (or future checkout) completes payment.
    """
    amount = round(price_cents / 100.0, 2)
    lines = [{
        "title": line_label,
        "quantity": max(1, int(qty)),
        "price": f"{amount:.2f}",
    }]
    draft_input: dict = {
        "note": note[:200] or f"OddHobb studio order · {line_label}",
        "lineItems": lines,
    }
    if email:
        draft_input["email"] = email[:120]
    query = """
    mutation draftOrderCreate($input: DraftOrderInput!) {
      draftOrderCreate(input: $input) {
        draftOrder { id name invoiceUrl totalPriceSet { shopMoney { amount currencyCode } } }
        userErrors { field message }
      }
    }
    """
    data = gql(query, {"input": draft_input})
    err = data.get("errors")
    if err:
        return {"ok": False, "error": str(err)[:300], "configured": True}
    res = ((data.get("data") or {}).get("draftOrderCreate")) or {}
    user_errors = res.get("userErrors") or []
    draft = res.get("draftOrder") or {}
    if user_errors:
        return {"ok": False, "error": user_errors[0].get("message", "draft failed"),
                "user_errors": user_errors}
    return {
        "ok": bool(draft),
        "draft_id": draft.get("id"),
        "name": draft.get("name"),
        "invoice_url": draft.get("invoiceUrl") or "",
        "total": (draft.get("totalPriceSet") or {}).get("shopMoney") or {},
        "store": store(),
    }
