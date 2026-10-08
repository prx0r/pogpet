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

API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2026-07").strip() or "2026-07"

# Card P0 hidden product — one internal SKU, unpublished from the Online
# Store catalogue. OddHobb sells it; each personalised creation becomes
# line-item customAttributes, never a new Shopify product.
CARD_PRODUCT_SKU = os.environ.get("CARD_SHOPIFY_SKU", "ODD-CARD-5X7")
CARD_PRODUCT_TITLE = "OddHobb Personalised 5×7 Greeting Card"


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
    return _exchange()


def _exchange() -> str:
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

    def _post(tok: str) -> dict[str, Any]:
        req = urllib.request.Request(
            f"https://{store()}/admin/api/{API_VERSION}/graphql.json",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": tok,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return {"errors": "[API] Invalid API key or access token"}
            raise

    data = _post(_token())
    if isinstance(data, dict) and "Invalid API key" in str(data.get("errors") or ""):
        # stored token went stale (~24h) — fresh exchange, one retry
        data = _post(_exchange())
    return data


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
        "originalUnitPrice": f"{amount:.2f}",
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
        "api_version": API_VERSION,
    }


def create_card_draft_order(qty: int, price_cents: int, oddhobb_order_id: str,
                            design_id: str, revision: int, grammar: str = "",
                            prodigi_sku: str = "CLASSIC-GRE-FEDR-7X5-BLA") -> dict:
    """Card P0 checkout: one hidden line item + customAttributes.

    Shopify owns payment + shipping + order ledger; OddHobb owns what is
    being made; Prodigi owns manufacture. No source photos leave us —
    Shopify only gets enough to identify the frozen OddHobb order.
    """
    amount = round(price_cents / max(1, int(qty)) / 100.0, 2)
    lines = [{
        "title": CARD_PRODUCT_TITLE,
        "quantity": max(1, int(qty)),
        "originalUnitPrice": f"{amount:.2f}",
        "sku": CARD_PRODUCT_SKU,
        "customAttributes": [
            {"key": "oddhobb_order_id", "value": oddhobb_order_id[:64]},
            {"key": "design_id", "value": design_id[:64]},
            {"key": "revision", "value": str(revision)},
            {"key": "grammar", "value": (grammar or "")[:32]},
            {"key": "prodigi_sku", "value": prodigi_sku[:64]},
        ],
    }]
    draft_input: dict = {
        "note": f"OddHobb card {oddhobb_order_id} · {design_id} r{revision} · {grammar}"[:200],
        "lineItems": lines,
        "taxExempt": False,
    }
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
        "api_version": API_VERSION,
        "sku": CARD_PRODUCT_SKU,
    }


def verify_webhook(data: bytes, hmac_header: str) -> bool:
    """Verify a Shopify webhook HMAC (X-Shopify-Hmac-Sha256) with the app secret."""
    import base64
    import hashlib
    import hmac as _hmac
    secret = _env("SHOPIFY_API_SECRET")
    if not secret or not hmac_header:
        return False
    digest = _hmac.new(secret.encode(), data, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    # constant-time compare, tolerate hex vs base64 misconfig
    import hmac as _h
    return _h.compare_digest(expected, hmac_header.strip())
