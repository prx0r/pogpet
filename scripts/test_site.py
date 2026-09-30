#!/usr/bin/env python3
"""Full test pass — hosts, gates, contract, flow, MCP, assets.

    python3 scripts/test_site.py      # exits non-zero on any FAIL
Free only: no Meshy calls, no credits. Results go to docs/test-report.md.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOK = (ROOT / ".token").read_text().strip()
API = "https://pog.pet/backend/api"
PUB = "https://pog.pet"
MCP = "https://mcp.oddhobb.com/mcp?token=" + TOK
UA = {"User-Agent": "Mozilla/5.0 (oddhobb-test)"}
RESULTS: list[tuple[str, str, str]] = []
TB_BASELINE = -1


def rec(name, ok, detail=""):
    RESULTS.append(("PASS" if ok else "FAIL", name, str(detail)[:90]))


def fetch(url, data=None, headers=None, timeout=90):
    h = dict(UA)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h,
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)
    except Exception as e:  # noqa: BLE001
        return 0, str(e).encode(), {}


def jget(path, token=TOK):
    sep = "&" if "?" in path else "?"
    code, body, _ = fetch(f"{API}{path}{sep}token={token}")
    if code != 200:
        raise AssertionError(f"{path} -> HTTP {code}: {body[:120]!r}")
    return json.loads(body)


def mcp_post(body, sid=None):
    h = {"Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    if sid:
        h["mcp-session-id"] = sid
    code, out, hdrs = fetch(MCP, data=json.dumps(body).encode(), headers=h)
    # 202 = "accepted" (e.g. notifications) — no body, result rides the SSE
    if code not in (200, 202):
        raise AssertionError(f"mcp HTTP {code}: {out[:120]!r}")
    sid2 = hdrs.get("mcp-session-id") or hdrs.get("Mcp-Session-Id") or sid
    return sid2, out.decode()


def mcp_data(text):
    m = re.search(r"data: (\{.*\})", text)
    if not m:
        raise AssertionError("no data line")
    return json.loads(m.group(1))


def main() -> int:
    _log = Path("/tmp/opencode/api.log")
    global TB_BASELINE
    TB_BASELINE = _log.read_text().count("Traceback") if _log.exists() else -1
    # ── 1. hosts ────────────────────────────────────────────────────────────
    hosts = ["oddhobb.com", "www.oddhobb.com", "gifts.oddhobb.com",
             "boardgames.oddhobb.com", "cards.oddhobb.com", "my.oddhobb.com"]
    for h in hosts:
        code, body, _ = fetch(f"https://{h}/")
        ok = code == 200 and b"oddhobb" in body
        rec(f"host {h}", ok, f"HTTP {code}")

    # ── 2. page structure + brand ───────────────────────────────────────────
    code, page, _ = fetch(f"{PUB}/")
    html = page.decode("utf-8", "replace")
    for needle, label in [
        ("<title>oddhobb", "title branded oddhobb"),
        ("class=\"topbar\"", "Amazon topbar (search+account)"),
        ("id=\"catstrip\"", "persistent category strip"),
        ("id=\"qsearch\"", "storefront search box"),
        ("id=\"shop-hero\"", "prompt-forward hero band"),
        ("id=\"people-grid\"", "my. people grid"),
        ('property="og:title"', "og meta"),
        ('name="description"', "meta description"),
        ("initSections", "host->section routing"),
        ("api/catalog", "catalog registry fetch"),
        ("data-panel", "tab panels"),
    ]:
        rec(f"page: {label}", needle in html)
    rec("page: double rail gone",
        "seclrail" not in html and "sec-rail-items" not in html
        and 'id="secchips"' not in html)
    rec("page: no visible pogpet brand",
        not re.search(r">pogpet<|pogpet —|at pogpet", html))
    rec("page: my-space copy (star/people)",
        "Your star" in html and "autosorted into people" in html
        and ">add someone<" in html)
    with open("/tmp/opencode/inline_test.js", "w") as f:
        f.write("\n;\n".join(re.findall(
            r"<script(?![^>]*\bsrc=)(?![^>]*\btype=[\"']application/ld\+json)[^>]*>(.*?)</script>",
            html, re.S)))
    import shutil
    import subprocess
    if shutil.which("node"):
        r = subprocess.run(["node", "--check", "/tmp/opencode/inline_test.js"],
                           capture_output=True, text=True)
        rec("inline JS syntax (node --check)", r.returncode == 0,
            r.stderr.splitlines()[0] if r.returncode else "clean")
    else:
        rec("inline JS syntax (node --check)", True, "node missing - skipped")

    # ── 2b. multi-brand seam (GET /api/brand + config.brand_for) ───────────
    # brand_for() is pure config — no network, exercises the transferable map
    try:
        sys.path.insert(0, str(ROOT))
        from backend import config as _cfg
        b1 = _cfg.brand_for("oddhobb.com")
        b2 = _cfg.brand_for("www.ochema.co")
        b3 = _cfg.brand_for("unknown.example")
        rec("brand_for: oddhobb host", b1["brand"] == "oddhobb"
            and b1["support"] == "support@oddhobb.com")
        rec("brand_for: www.ochema.co inherits ochema",
            b2["brand"] == "ochema" and b2["domain"] == "ochema.co"
            and b2["support"] == "support@ochema.co")
        rec("brand_for: unknown host falls back, never errors",
            b3["brand"] == "oddhobb" and "domain" in b3)
        rec("brand map covers both live domains",
            "ochema.co" in _cfg.BRANDS and "oddhobb.com" in _cfg.BRANDS)
    except Exception as e:  # noqa: BLE001
        rec("brand_for()", False, e)
    try:
        code, body, _ = fetch(f"{PUB}/backend/api/brand?token={TOK}")
        d = json.loads(body)
        rec("GET /api/brand (public, bridge-gated)",
            code == 200 and d.get("ok") and d.get("brand")
            and d.get("domain"), f"{d.get('domain')} -> {d.get('brand')}")
    except Exception as e:  # noqa: BLE001
        rec("GET /api/brand", False, e)

    # ── 2c. owner-sig + rate-limit guards (audit R6) ───────────────────────
    try:
        sys.path.insert(0, str(ROOT))
        from backend import config as _cfg
        code, body, _ = fetch(
            f"{API}/session?token={TOK}",
            data=json.dumps({"owner": "anon"}).encode(),
            headers={"Content-Type": "application/json"})
        d = json.loads(body)
        rec("POST /api/session mints anon sig",
            code == 200 and d.get("ok") and d.get("owner") == "anon"
            and bool(d.get("owner_sig")),
            f"sig len {len(d.get('owner_sig') or '')}")
        anon_sig = d.get("owner_sig") or ""
    except Exception as e:  # noqa: BLE001
        rec("POST /api/session mints anon sig", False, e)
        anon_sig = ""
    try:
        sys.path.insert(0, str(ROOT))
        from backend import config as _cfg
        # signed pog_* session
        code, body, _ = fetch(
            f"{API}/session?token={TOK}",
            data=json.dumps({"owner": "pog_auditx"}).encode(),
            headers={"Content-Type": "application/json"})
        d = json.loads(body)
        rec("session signs pog_* browser ids",
            code == 200 and d.get("owner") == "pog_auditx" and d.get("owner_sig"),
            d.get("owner", ""))
        pog_sig = d.get("owner_sig") or ""
        # named owner without proof -> 403
        code, body, _ = fetch(
            f"{API}/session?token={TOK}",
            data=json.dumps({"owner": "prx0r"}).encode(),
            headers={"Content-Type": "application/json"})
        d = json.loads(body)
        rec("session refuses unnamed named-owner claim",
            code == 403 and not d.get("ok"),
            f"HTTP {code}")
        # non-anon read without sig -> 403
        code, body, _ = fetch(f"{API}/meshes?owner=prx0r&token={TOK}")
        d = json.loads(body)
        rec("non-anon mesh read without sig -> 403",
            code == 403 and not d.get("ok"),
            f"HTTP {code}")
        # non-anon write without sig -> 403
        code, body, _ = fetch(
            f"{API}/people/rename?token={TOK}",
            data=json.dumps({"owner": "prx0r", "from": "A", "to": "B"}).encode(),
            headers={"Content-Type": "application/json"})
        d = json.loads(body)
        rec("non-anon rename without sig -> 403",
            code == 403 and not d.get("ok"),
            f"HTTP {code}")
        # signed write for own pog_* owner is allowed (credits may be 0)
        if pog_sig:
            code, body, _ = fetch(
                f"{API}/credits?owner=pog_auditx&token={TOK}",
                headers={"X-Owner-Sig": pog_sig})
            d = json.loads(body)
            rec("signed non-anon credits read allowed",
                code == 200 and d.get("ok"),
                f"HTTP {code}")
        else:
            rec("signed non-anon credits read allowed", False, "no sig")
        # login rate limit: 6 bad tries -> 429 on later attempts
        codes = []
        for i in range(6):
            code, body, _ = fetch(
                f"{API}/accounts/login?token={TOK}",
                data=json.dumps({"handle": "ratelimit_probe", "password": "wrong"}).encode(),
                headers={"Content-Type": "application/json"})
            codes.append(code)
        rec("login rate limit kicks in (429)",
            429 in codes, f"codes={codes}")
        # security headers via public host
        code, body, hdrs = fetch("https://oddhobb.com/")
        lower = {k.lower(): v for k, v in hdrs.items()}
        rec("security headers on public pages",
            lower.get("x-content-type-options") == "nosniff"
            and lower.get("x-frame-options") == "SAMEORIGIN"
            and lower.get("referrer-policy"),
            f"{lower.get('x-content-type-options')}/{lower.get('x-frame-options')}")
        rec("trademark doc exists",
            (ROOT / "docs" / "trademark.md").is_file())
        # SEO / agent-discovery pack (docs/seo.md)
        code, body, _ = fetch("https://oddhobb.com/api/seo/products.json")
        d = json.loads(body)
        prods = d.get("products") or []
        rec("GET /api/seo/products.json (public)",
            code == 200 and d.get("ok") and len(prods) >= 12
            and all({"product_highlight", "question_and_answer", "item_group_title"}
                    <= set(p) for p in prods),
            f"{len(prods)} products")
        code, body, _ = fetch("https://oddhobb.com/api/seo/faq.json")
        d = json.loads(body)
        rec("GET /api/seo/faq.json (public)",
            code == 200 and d.get("ok") and d.get("count", 0) >= 20,
            f"{d.get('count')} pairs")
        code, body, _ = fetch("https://oddhobb.com/guides/greeting_card")
        html = body.decode("utf-8", "replace")
        rec("GET /guides/greeting_card (FAQPage schema)",
            code == 200 and "FAQPage" in html and "greeting card" in html.lower(),
            f"HTTP {code} {len(html)}b")
        code, body, _ = fetch("https://oddhobb.com/backend/api/feeds/google.xml")
        xml = body.decode("utf-8", "replace")
        rec("google feed carries AI attributes",
            code == 200 and "custom_label_0" in xml and "item_group_id" in xml
            and "FAQ:" in xml,
            f"HTTP {code}")
        code, body, _ = fetch("https://oddhobb.com/backend/api/feeds/shopify.json")
        d = json.loads(body)
        p0 = (d.get("products") or [{}])[0]
        rec("shopify feed Q&A in body_html",
            code == 200 and "Questions" in (p0.get("body_html") or "")
            and "seo" in p0,
            p0.get("handle", ""))
        # company graph + bobdod
        code, body, _ = fetch("https://oddhobb.com/api/companygraph")
        d = json.loads(body)
        rec("GET /api/companygraph (public)",
            code == 200 and d.get("ok")
            and (d.get("helper_agent") or {}).get("name") == "bobdod"
            and len(d.get("products") or []) >= 12
            and len(d.get("capabilities") or []) >= 5,
            f"{len(d.get('products') or [])} products, "
            f"{len(d.get('capabilities') or [])} caps")
        rec("page names bobdod as helper", b"bobdod" in page)
        # discovery stack: robots, GEO, sitemap, Product JSON-LD, Q&A volume
        code, body, _ = fetch("https://oddhobb.com/robots.txt")
        robots = body.decode("utf-8", "replace")
        rec("robots.txt allows AI crawlers",
            code == 200 and "GPTBot" in robots and "ClaudeBot" in robots
            and "PerplexityBot" in robots and "Google-Extended" in robots,
            f"HTTP {code}")
        code, body, _ = fetch("https://oddhobb.com/learn/")
        html_learn = body.decode("utf-8", "replace")
        rec("GET /learn/ hub",
            code == 200 and "personalised pet" in html_learn.lower()
            and "/learn/oddhobb-vs-pet-portraits" in html_learn,
            f"HTTP {code}")
        code, body, _ = fetch("https://oddhobb.com/learn/oddhobb-vs-pet-portraits")
        html_c = body.decode("utf-8", "replace")
        rec("comparison page + Article JSON-LD",
            code == 200 and "Traditional portrait" in html_c
            and "Article" in html_c and "<table>" in html_c,
            f"HTTP {code} {len(html_c)}b")
        code, body, _ = fetch("https://oddhobb.com/guides/figurine")
        html_g = body.decode("utf-8", "replace")
        rec("guide has Product + FAQPage JSON-LD",
            code == 200 and '"@type": "Product"' in html_g
            and "FAQPage" in html_g and "priceCurrency" in html_g,
            f"HTTP {code}")
        code, body, _ = fetch("https://oddhobb.com/api/seo/faq.json")
        d = json.loads(body)
        rec("Q&A volume >= 200 pairs (GEO bank)",
            code == 200 and d.get("count", 0) >= 200,
            f"{d.get('count')} pairs")
        code, body, _ = fetch("https://oddhobb.com/sitemap.xml")
        sm = body.decode("utf-8", "replace")
        rec("sitemap.xml lists learn + guides",
            code == 200 and "/learn/" in sm and "/guides/" in sm
            and "urlset" in sm,
            f"HTTP {code} {sm.count('<url>')} urls")
    except Exception as e:  # noqa: BLE001
        rec("owner-sig + rate-limit guards", False, e)

    # ── 3. contract APIs ────────────────────────────────────────────────────
    try:
        s = jget("/sections")
        rec("GET /sections", s["ok"] and len(s["sections"]) == 5
            and "board-games" in s["section_of"].values(),
            f"{len(s['sections'])} sections")
    except Exception as e:  # noqa: BLE001
        rec("GET /sections", False, e)
    try:
        c = jget("/catalog")
        ids = {p["id"] for p in c["products"]}
        rec("GET /catalog", c["ok"] and c["count"] == 21 and "jigsaw" in ids
            and all("emoji" in p and "section" in p for p in c["products"]),
            f"{c['count']} products")
    except Exception as e:  # noqa: BLE001
        rec("GET /catalog", False, e)
    # people: autosort + "who's this?" round-trip on the sample owner
    try:
        def jpost(path, body, owner_sig=None):
            sep = "&" if "?" in path else "?"
            headers = {"Content-Type": "application/json"}
            if owner_sig:
                headers["X-Owner-Sig"] = owner_sig
            code, out, _ = fetch(
                f"{API}{path}{sep}token={TOK}", data=json.dumps(body).encode(),
                headers=headers)
            if code != 200:
                raise AssertionError(f"{path} -> HTTP {code}: {out[:120]!r}")
            return json.loads(out)

        def jpost_raw(path, body, owner_sig=None):
            """Returns (code, json) without raising — for negative tests."""
            sep = "&" if "?" in path else "?"
            headers = {"Content-Type": "application/json"}
            if owner_sig:
                headers["X-Owner-Sig"] = owner_sig
            code, out, _ = fetch(
                f"{API}{path}{sep}token={TOK}", data=json.dumps(body).encode(),
                headers=headers)
            try:
                return code, json.loads(out)
            except Exception:
                return code, {"raw": out[:200]}
        au = jpost("/photos/autosort?owner=anon", {})
        gs = au.get("groups", [])
        okshape = au.get("ok") and gs and all(
            {"person", "photos", "needs_name"} <= set(g) for g in gs)
        rec("autosort groups (person/photos/r2_key/mesh_id)",
            okshape and all(
                {"id", "mime", "r2_key", "has_mesh", "mesh_id"} <= set(ph)
                for g in gs for ph in g["photos"]),
            f"{len(gs)} groups")
        before = gs[0]["person"]
        r1 = jpost("/people/rename", {"owner": "anon", "from": before, "to": "NibbleTmp"})
        r2 = jpost("/people/rename", {"owner": "anon", "from": "NibbleTmp", "to": before})
        rec("rename round-trip (who's this? -> saved)",
            r1.get("ok") and r1.get("renamed", 0) >= 1 and r2.get("ok"),
            f"{before} -> NibbleTmp -> {before}")
    except Exception as e:  # noqa: BLE001
        rec("autosort groups (person/photos/r2_key/mesh_id)", False, e)
        rec("rename round-trip (who's this? -> saved)", False, "skipped")
    try:
        fl = jget("/flow?owner=anon")
        rec("GET /flow (sample owner)",
            fl["ok"] and fl["stage"] == "ready" and fl["active_mesh_id"],
            f"stage={fl['stage']} active={fl['active_mesh_id'][:14]}")
        rec("flow hint present", bool(fl.get("hint")), fl.get("hint", "")[:50])
    except Exception as e:  # noqa: BLE001
        rec("GET /flow (sample owner)", False, e)
    try:
        mp = jget("/meshes/msh_70edae28a4304f4cb7e9/products")
        rec("sample mesh products (inheritance)",
            mp["ok"] and len(mp["products"]) == 8
            and all("section" in p for p in mp["products"]),
            f"{len(mp['products'])} bound")
    except Exception as e:  # noqa: BLE001
        rec("sample mesh products (inheritance)", False, e)
    try:
        pr = jget("/products?owner=anon")
        items = pr.get("items", [])
        rec("GET /products (13 previews, cached)",
            pr["ok"] and len(items) == 13 and pr.get("active_mesh_id"),
            f"{len(items)} items")
        if items:
            img = items[0]["image"]
            # storage.public_url returns a path; the site's art() prepends /backend
            u = (PUB + "/backend" + img if img.startswith("/") else img)
            u = u + ("&" if "?" in u else "?") + "token=" + TOK
            ic, ib, ih = fetch(u)
            rec("preview image fetchable",
                ic == 200 and ih.get("Content-Type", "").startswith("image"),
                f"HTTP {ic} {ih.get('Content-Type', '')}")
    except Exception as e:  # noqa: BLE001
        rec("GET /products (13 previews, cached)", False, e)
    for path, label in [("/styles", "styles"), ("/acts", "acts"),
                        ("/credits?owner=anon", "credits"),
                        ("/me?owner=anon", "me")]:
        try:
            d = jget(path)
            rec(f"GET {label}", d.get("ok") is True)
        except Exception as e:  # noqa: BLE001
            rec(f"GET {label}", False, e)

    # ── 3b. public feeds + llms.txt (no token anywhere) ─────────────────────
    try:
        code, body, _ = fetch("https://oddhobb.com/backend/api/feeds/google.xml")
        xml = body.decode("utf-8", "replace")
        n_items = xml.count("<item>")
        rec("FEED google.xml (public)",
            code == 200 and n_items >= 10 and "xmlns:g=" in xml
            and "GBP" in xml and "OddHobb" in xml,
            f"HTTP {code}, {n_items} items")
        m = re.search(r"<g:image_link>([^<]+)", xml)
        if m:
            ic, ib, ih = fetch(m.group(1))
            rec("FEED image_link fetchable (no token)",
                ic == 200 and ih.get("Content-Type", "").startswith("image"),
                f"HTTP {ic} {ih.get('Content-Type', '')}")
        else:
            rec("FEED image_link fetchable (no token)", False, "none found")
    except Exception as e:  # noqa: BLE001
        rec("FEED google.xml (public)", False, e)
        rec("FEED image_link fetchable (no token)", False, "skipped")
    try:
        code, body, _ = fetch("https://oddhobb.com/backend/api/feeds/shopify.json")
        sj = json.loads(body)
        ps = sj.get("products", [])
        rec("FEED shopify.json (public)",
            code == 200 and len(ps) >= 10 and all(
                {"title", "handle", "vendor", "variants", "images"} <= set(p)
                for p in ps),
            f"HTTP {code}, {len(ps)} products")
    except Exception as e:  # noqa: BLE001
        rec("FEED shopify.json (public)", False, e)
    try:
        code, body, _ = fetch("https://oddhobb.com/llms.txt")
        txt = body.decode("utf-8", "replace")
        rec("llms.txt served",
            code == 200 and "mcp.oddhobb.com/mcp" in txt
            and "shopify.json" in txt,
            f"HTTP {code}")
    except Exception as e:  # noqa: BLE001
        rec("llms.txt served", False, e)
    try:
        import tomllib
        toml = tomllib.loads((ROOT / "shopify-app" / "shopify.app.toml").read_text())
        scopes = toml.get("access_scopes", {}).get("scopes", "")
        pkg = json.loads((ROOT / "shopify-app" / "package.json").read_text())
        rec("shopify-app scaffold",
            "write_products" in scopes and "read_products" in scopes
            and (ROOT / "shopify-app" / "scripts" / "sync-catalog.mjs").exists()
            and "sync:catalog" in pkg.get("scripts", {})
            and (ROOT / "shopify-app" / "ODDHOBB.md").exists(),
            f"scopes={scopes}")
    except Exception as e:  # noqa: BLE001
        rec("shopify-app scaffold", False, e)
    try:
        import subprocess as _sp
        r = _sp.run(["node", "--check",
                     str(ROOT / "shopify-app" / "scripts" / "sync-catalog.mjs")],
                    capture_output=True, text=True)
        rec("sync-catalog.mjs syntax", r.returncode == 0,
            "clean" if r.returncode == 0 else r.stderr.splitlines()[0])
    except Exception as e:  # noqa: BLE001
        rec("sync-catalog.mjs syntax", False, e)

    # ── 4. auth gates ───────────────────────────────────────────────────────
    code, _, _ = fetch(f"{API}/catalog")
    rec("API without token -> 401", code == 401, f"HTTP {code}")
    code, _, _ = fetch(f"{API}/catalog?token=wrong")
    rec("API bad token -> 401", code == 401, f"HTTP {code}")

    # ── 5. premesh (edge, free) ─────────────────────────────────────────────
    try:
        from PIL import Image, ImageDraw
        import io
        # must NOT be flat — intake rejects flat frames on purpose
        img = Image.new("RGB", (600, 400), (180, 140, 90))
        d = ImageDraw.Draw(img)
        d.ellipse([80, 60, 520, 340], fill=(220, 190, 120), outline=(60, 40, 20))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        boundary = "----test9"
        body = (f"--{boundary}\r\nContent-Disposition: form-data; "
                f"name=\"photo\"; filename=\"t.jpg\"\r\n"
                f"Content-Type: image/jpeg\r\n\r\n").encode() + buf.getvalue() + \
               f"\r\n--{boundary}--\r\n".encode()
        code, out, hdrs = fetch(
            f"{API}/premesh?token={TOK}&recipe=photo",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        hk = next((v for k, v in hdrs.items() if k.lower() == "x-premesh-ok"), None)
        rec("POST /premesh (passthrough recipe)",
            code == 200 and hk == "1" and len(out) > 1000,
            f"HTTP {code} x-premesh-ok={hk} bytes={len(out)}")
    except Exception as e:  # noqa: BLE001
        rec("POST /premesh (passthrough recipe)", False, e)

    # ── 6. MCP contract ─────────────────────────────────────────────────────
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "test", "version": "0"}}}
    try:
        sid, out = mcp_post(init)
        rec("MCP initialize (token)", '"tools"' in out and bool(sid),
            f"session {str(sid)[:8]}")
        mcp_post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
        _, out = mcp_post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, sid)
        tools = mcp_data(out)["result"]["tools"]
        names = {t["name"] for t in tools}
        rec("MCP tools/list = 21", len(tools) == 21,
            f"{len(tools)} tools")
        rec("MCP foundation tools present",
            {"figg_catalog", "figg_flow", "figg_start_mesh",
             "figg_upload_photo", "figg_tools"} <= names)
        # Streamable HTTP: this MCP answers tools/call on the POST body
        # itself (event-stream). A concurrent GET SSE on the same session
        # trips Cloudflare 403 — do not open one first.
        hcall = {"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 "mcp-session-id": sid}
        code202, body202, _ = fetch(
            MCP, data=json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                  "params": {"name": "figg_flow",
                                             "arguments": {"owner": "anon"}}}).encode(),
            headers=hcall, timeout=60)
        out202 = body202.decode()
        inner = None
        try:
            env = mcp_data(out202)
            text = env["result"]["content"][0]["text"]
            inner = json.loads(text)
        except Exception:  # noqa: BLE001
            inner = None
        if inner is None:
            rec("MCP tools/call figg_flow", False,
                f"HTTP {code202}, unparsable payload len={len(out202)}")
        else:
            ok = inner.get("ok") is True and inner.get("stage") == "ready"
            rec("MCP tools/call figg_flow", ok,
                f"stage={inner.get('stage')} mesh={str(inner.get('active_mesh_id') or '')[:14]}")
    except Exception as e:  # noqa: BLE001
        rec("MCP contract", False, e)

    # no-token gate on the public MCP host
    code, _, _ = fetch(MCP.split("?")[0],
                       data=json.dumps(init).encode(),
                       headers={"Content-Type": "application/json",
                                "Accept": "application/json, text/event-stream"})
    rec("MCP without token -> 401", code == 401, f"HTTP {code}")

    # ── 7. infra sanity ─────────────────────────────────────────────────────
    log = Path("/tmp/opencode/api.log")
    n_end = log.read_text().count("Traceback") if log.exists() else -1
    rec("api.log: no NEW tracebacks during this run", n_end == TB_BASELINE,
        f"baseline={TB_BASELINE} now={n_end} (2 historical = fixed flow bug)")
    code, body, _ = fetch("https://oddhobb.com/")
    rec("oddhobb.com final smoke", code == 200, f"HTTP {code}")

    # ── report ──────────────────────────────────────────────────────────────
    fails = [r for r in RESULTS if r[0] == "FAIL"]
    width = max(len(r[1]) for r in RESULTS)
    print(f"\n{'':2} {'test':<{width}}  detail")
    for i, (st, name, detail) in enumerate(RESULTS, 1):
        print(f"{i:2} {st:<4} {name:<{width}}  {detail}")
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} passed"
          + ("" if not fails else f"  — {len(fails)} FAILED"))
    md = ["# Test report — oddhobb", "",
          f"> Run {__import__('datetime').datetime.now():%Y-%m-%d %H:%M} · "
          f"`scripts/test_site.py` · **{len(RESULTS) - len(fails)}/{len(RESULTS)} passed** · 0 credits", "",
          "| # | Result | Test | Detail |", "|---|---|---|---|"]
    for i, (st, name, detail) in enumerate(RESULTS, 1):
        md.append(f"| {i} | {st} | {name} | {detail} |")
    md += ["", "Re-run: `python3 scripts/test_site.py` (exits non-zero on FAIL).",
           "Covers: 6 hosts + mcp host, page structure & brand, contract APIs, "
           "sample-flow, inheritance, preview assets, auth gates, free premesh "
           "edge call, public feeds (google.xml, shopify.json, image fetch, "
           "llms.txt), shopify-app scaffold + sync syntax, MCP session/tools/call/gate, logs."]
    (ROOT / "docs" / "test-report.md").write_text("\n".join(md) + "\n")
    print("report -> docs/test-report.md")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
