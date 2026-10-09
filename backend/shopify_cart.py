"""Shopify Storefront Cart API — customer basket, no Admin secrets involved.

Browser never sees tokens: every call below runs server-side. Needs:
  SHOPIFY_STOREFRONT_TOKEN  (Storefront API access token, public channel)
  SHOPIFY_CARD_VARIANT_ID   (gid://shopify/ProductVariant/… of ODD-CARD-5X7)
Without them every function returns {ok:False} naming the exact unblock —
never a faked cart. Admin API (drafts) stays a separate module.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

API_VERSION = os.environ.get("SHOPIFY_STOREFRONT_VERSION", "2025-10")


def _store() -> str:
    return (os.environ.get("SHOPIFY_STORE") or "").strip().replace("https://", "").rstrip("/")


def _token() -> str:
    return (os.environ.get("SHOPIFY_STOREFRONT_TOKEN") or "").strip()


def _variant() -> str:
    return (os.environ.get("SHOPIFY_CARD_VARIANT_ID") or "").strip()


def variant_for(product: str = "greeting_card") -> str:
    """product/line id → Shopify variant GID. Optional JSON map in
    SHOPIFY_VARIANTS_JSON (e.g. {"greeting_card":"gid://…","golf_marker":"gid://…"});
    falls back to the single card variant for cards, empty otherwise."""
    try:
        import json as _json
        m = _json.loads(os.environ.get("SHOPIFY_VARIANTS_JSON") or "{}")
        if isinstance(m, dict) and m.get(product):
            return str(m[product]).strip()
    except Exception:  # noqa: BLE001
        pass
    if product in ("greeting_card", "card", ""):
        return _variant()
    return ""


def ready() -> tuple[bool, str]:
    if not _store():
        return False, "SHOPIFY_STORE is not set"
    if not _token():
        return False, "SHOPIFY_STOREFRONT_TOKEN is not set — create a Storefront access token (headless channel) and paste it into .env"
    if not _variant():
        return False, "SHOPIFY_CARD_VARIANT_ID is not set — create the ODD-CARD-5X7 product on the live store and paste its variant GID into .env (extra lines go in SHOPIFY_VARIANTS_JSON)"
    return True, ""


def gql(query: str, variables: dict | None = None) -> dict:
    ok, err = ready()
    if not ok:
        return {"ok": False, "error": err}
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        f"https://{_store()}/api/{API_VERSION}/graphql.json", data=body,
        headers={"Content-Type": "application/json",
                 "X-Shopify-Storefront-Access-Token": _token(),
                 "User-Agent": "OddHobb/1.0 (factory-cart)"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"storefront HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"storefront unreachable: {e}"}
    if d.get("errors"):
        return {"ok": False, "error": str(d["errors"][0].get("message", "graphql error"))[:200]}
    return {"ok": True, "data": d.get("data") or {}}


_CART_FRAG = """id checkoutUrl totalQuantity estimatedCost { totalAmount { amount currencyCode } }
  lines(first: 50) { edges { node { id quantity
    merchandise { ... on ProductVariant { id title price { amount currencyCode } } }
    attributes { key value } } } }"""


def cart_create(design_id: str, revision: int, qty: int, oddhobb_order_id: str,
                product: str = "greeting_card", line: str = "") -> dict:
    """One personalised creation → new cart. Line carries design linkage only —
    never photos, tokens or URLs."""
    gid = variant_for(product)
    if not gid:
        return {"ok": False, "error": f"no Shopify variant mapped for {product!r} — add it to SHOPIFY_VARIANTS_JSON"}
    r = gql("""mutation cartCreate($input: CartInput!) {
      cartCreate(input: $input) { cart { %s } userErrors { field message } } }""" % _CART_FRAG,
        {"input": {"lines": [{"merchandiseId": gid, "quantity": max(1, int(qty or 1)),
                              "attributes": [{"key": "design_id", "value": design_id[:64]},
                                             {"key": "revision", "value": str(revision)},
                                             {"key": "oddhobb_order_id", "value": oddhobb_order_id[:64]},
                                             {"key": "line", "value": (line or product)[:32]}]}]}})
    if not r.get("ok"):
        return r
    cc = (r["data"].get("cartCreate") or {})
    if cc.get("userErrors"):
        return {"ok": False, "error": str(cc["userErrors"][0].get("message", "cart failed"))[:200]}
    cart = cc.get("cart") or {}
    if not cart.get("id"):
        return {"ok": False, "error": "cartCreate returned no cart"}
    return {"ok": True, "cart": cart}


def cart_lines_add(cart_id: str, design_id: str, revision: int, qty: int,
                   oddhobb_order_id: str, product: str = "greeting_card",
                   line: str = "") -> dict:
    gid = variant_for(product)
    if not gid:
        return {"ok": False, "error": f"no Shopify variant mapped for {product!r} — add it to SHOPIFY_VARIANTS_JSON"}
    r = gql("""mutation cartLinesAdd($cartId: ID!, $lines: [CartLineInput!]!) {
      cartLinesAdd(cartId: $cartId, lines: $lines) { cart { %s } userErrors { field message } } }""" % _CART_FRAG,
        {"cartId": cart_id,
         "lines": [{"merchandiseId": gid, "quantity": max(1, int(qty or 1)),
                    "attributes": [{"key": "design_id", "value": design_id[:64]},
                                   {"key": "revision", "value": str(revision)},
                                   {"key": "oddhobb_order_id", "value": oddhobb_order_id[:64]},
                                   {"key": "line", "value": (line or product)[:32]}]}]})
    if not r.get("ok"):
        return r
    ca = (r["data"].get("cartLinesAdd") or {})
    if ca.get("userErrors"):
        return {"ok": False, "error": str(ca["userErrors"][0].get("message", "add failed"))[:200]}
    return {"ok": True, "cart": ca.get("cart") or {}}


def cart_lines_update(cart_id: str, line_id: str, qty: int) -> dict:
    if int(qty) <= 0:
        return cart_lines_remove(cart_id, line_id)
    r = gql("""mutation cartLinesUpdate($cartId: ID!, $lines: [CartLineUpdateInput!]!) {
      cartLinesUpdate(cartId: $cartId, lines: $lines) { cart { %s } userErrors { field message } } }""" % _CART_FRAG,
        {"cartId": cart_id, "lines": [{"id": line_id, "quantity": int(qty)}]})
    if not r.get("ok"):
        return r
    cu = (r["data"].get("cartLinesUpdate") or {})
    if cu.get("userErrors"):
        return {"ok": False, "error": str(cu["userErrors"][0].get("message", "update failed"))[:200]}
    return {"ok": True, "cart": cu.get("cart") or {}}


def cart_lines_remove(cart_id: str, line_id: str) -> dict:
    r = gql("""mutation cartLinesRemove($cartId: ID!, $lineIds: [ID!]!) {
      cartLinesRemove(cartId: $cartId, lineIds: $lineIds) { cart { %s } userErrors { field message } } }""" % _CART_FRAG,
        {"cartId": cart_id, "lineIds": [line_id]})
    if not r.get("ok"):
        return r
    cr = (r["data"].get("cartLinesRemove") or {})
    if cr.get("userErrors"):
        return {"ok": False, "error": str(cr["userErrors"][0].get("message", "remove failed"))[:200]}
    return {"ok": True, "cart": cr.get("cart") or {}}


def cart_get(cart_id: str) -> dict:
    r = gql("""query cart($id: ID!) { cart(id: $id) { %s } }""" % _CART_FRAG, {"id": cart_id})
    if not r.get("ok"):
        return r
    cart = (r["data"] or {}).get("cart")
    if not cart:
        return {"ok": False, "error": "cart expired or not found — create a new one"}
    return {"ok": True, "cart": cart}
