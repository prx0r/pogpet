"""OddHobb Factory MCP — manufacturing capability for developers/Blender.

Separate from the storefront MCP (backend/mcp_server.py): different buyers,
different trust. This server sells manufacturing (estimate/quote/order/track),
never personalised goods. Data-only sharing: suppliers.py, jlc_materials.json,
supplier_catalog.json, geometry.py, config.jlc_check.

    python3 -m backend.factory_mcp                  # stdio
    MCP_HTTP=1 FACTORY_PORT=8803 python3 -m backend.factory_mcp  # :8803/mcp
    PUBLIC_MCP=1 FACTORY_PORT=8804 python3 -m backend.factory_mcp  # public tier

Public tier (no key): tools, catalog, suppliers, estimate, analyze.
Keyed tier adds: quote, compare, order_prepare, order_confirm, track
(quote/order/track are needs_input stubs until JLC API approval lands).
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from backend import suppliers as _sup  # noqa: E402
from backend import geometry as _geo  # noqa: E402
from backend.config import jlc_check  # noqa: E402

PORT = int(os.environ.get("FACTORY_PORT", "8803"))
VERSION = "0.1.0"
ORDERS_ON = os.environ.get("FACTORY_ENABLE_ORDERS", "") in ("1", "true")


def _j(obj: dict) -> str:
    return json.dumps(obj)


def _catalog() -> dict:
    p = ROOT / "backend" / "jlc_materials.json"
    jlc = json.loads(p.read_text()) if p.exists() else {}
    p2 = ROOT / "backend" / "supplier_catalog.json"
    cat = json.loads(p2.read_text()) if p2.exists() else {}
    return {"jlc": jlc, "catalog_meta": cat.get("meta", {})}


mcp = MCPServer("oddhobb-factory", instructions=(
    "OddHobb Factory (oddhobb.com/factory): manufacturing capability for "
    "developers and Blender. Estimate and analyse freely; live quotes need "
    "JLC pricing-API approval (not yet granted — quote tools say so); "
    "ordering stays behind prepare→approve→confirm and is off by default. "
    "Prices are estimated/rough/list until a supplier quotes. Never invent "
    "a unit price."
))


async def factory_tools() -> str:
    """The self-describing library: every area and tool this server exposes."""
    areas = {a: [{"name": fn.__name__, "doc": (fn.__doc__ or "").strip().split("\n")[0]}
                 for fn in fns] for a, fns in TOOL_AREAS.items()}
    count = sum(len(v) for v in TOOL_AREAS.values()) + 1
    return _j({"ok": True, "count": count, "areas": areas})


async def factory_catalog(process: str = "") -> str:
    """JLC materials bible: every orderable material per process with build
    volumes, tolerances, walls and price anchors. Pass process (SLA/WJP/SLS/
    MJF/FDM/SLM/BJ/CNC/PCB) to narrow, or empty for the whole bible."""
    cat = _catalog()["jlc"]
    if not process:
        return _j({"ok": True, "summary": "JLC materials bible (see docs/jlc-materials.md for prose)",
                   "processes": list(cat.get("processes_3dp", {}).keys()) + ["CNC", "PCB"],
                   "quote_rules": cat.get("quote_rules", {})})
    key = process.upper()
    procs = cat.get("processes_3dp", {})
    if key in procs:
        return _j({"ok": True, "process": key, "detail": procs[key]})
    if key in ("CNC", "PCB"):
        return _j({"ok": True, "process": key, "detail": cat.get(key.lower(), {})})
    return _j({"status": "needs_input", "summary": f"unknown process {process!r}",
               "next_actions": ["pick one of: " + ", ".join(list(procs.keys()) + ["CNC", "PCB"])]})


async def factory_suppliers(lane: str = "") -> str:
    """The 16 manufacturing lanes: capabilities, order path, price basis and
    grade. Pass a lane id for one card, or empty for all labels."""
    lanes = {sid: {k: spec[k] for k in ("label", "home", "ships", "materials",
                                        "colors_max", "build_mm", "order",
                                        "dispatch_days", "min_qty")
                   if k in spec} for sid, spec in _sup.SUPPLIERS.items()}
    if not lane:
        return _j({"ok": True, "summary": "16 lanes (14 registry + JLC + Prodigi — see docs/supplier-catalog.md)",
                   "lanes": lanes,
                   "note": "jlc/prodigi live in backend/jlc_materials.json + supplier_catalog.json until registry widened"})
    spec = _sup.SUPPLIERS.get(lane)
    if not spec:
        return _j({"status": "needs_input", "summary": f"unknown lane {lane!r}",
                   "next_actions": ["pick one of: " + ", ".join(sorted(lanes))]})
    return _j({"ok": True, "lane": lane, "detail": spec})


def _jlc_rough(material: str = "PLA", volume_cm3: float | None = None,
               weight_g: float | None = None) -> dict:
    """Our own JLC estimator from published floors + $/g (no approval needed
    to PRICE; ordering still needs it). Returns ROUGH offer + decide-helper."""
    try:
        rp = _catalog()["jlc"].get("rough_pricing", {})
        mat = (material or "PLA").upper().replace(" ", "").replace("-", "")
        mmap = rp.get("material_to_process", {})
        proc = mmap.get(mat)
        if proc is None:
            for k, v in mmap.items():
                kn = (k or "").upper().replace(" ", "").replace("-", "")
                if kn and (kn in mat or mat in kn):
                    proc = v
                    break
        proc = proc or "FDM"
        table = rp.get("by_process", {}).get(proc, {})
        base = float(table.get("base_usd", 1.0))
        per_g = (table.get("per_g_usd") or {})
        rate = None
        for k, v in per_g.items():
            if v is not None and k.replace("-", "") in mat:
                rate = float(v)
                break
        est, basis = base, f"${base:g} list floor (geometry unpriced)"
        w = weight_g
        if w is None and volume_cm3 is not None and table.get("density"):
            w = volume_cm3 * float(table["density"])
        if rate is not None and w is not None:
            est = max(base, round(w * rate, 2))
            basis = f"${rate}/g x {w:.1f}g (published rate)"
        cents = round(est * 100)
        return {"offer": {"lane": "jlc", "grade": "ROUGH", "process": proc,
                          "subtotal_usd": est, "basis": basis,
                          "note": "our model, ex-tax/shipping — live quote wins"},
                "estimate": {"supplier": "jlc", "feasible": True, "gaps": [],
                             "est_cents": cents, "ccy": "USD", "basis": basis,
                             "dispatch_days": None}}
    except Exception as e:  # noqa: BLE001
        return {"offer": {"lane": "jlc", "grade": "ROUGH", "error": str(e)[:100]},
                "estimate": {"supplier": "jlc", "feasible": False, "gaps": [str(e)[:100]],
                             "est_cents": None, "ccy": "USD"}}


async def factory_estimate(material: str = "PLA", colors: int = 1,
                           dims_mm: list | None = None,
                           volume_cm3: float | None = None,
                           weight_g: float | None = None,
                           region: str = "UK") -> str:
    """Cheapest-capable lane ranking for a part: feasibility + est_cents or a
    named gap per lane. Labelled estimated — never orderable, live quotes win."""
    if dims_mm is not None:
        dims_mm = [float(d) for d in dims_mm]
    opts = _sup.options_for(material=material, colors=colors, dims_mm=dims_mm,
                            volume_cm3=volume_cm3, weight_g=weight_g, region=region)
    jr = _jlc_rough(material, volume_cm3, weight_g)
    opts = opts + [{"supplier": "jlc", "label": "JLC (own ROUGH model)",
                    "ships": ["worldwide"], "order": "quote",
                    "feasible": jr["estimate"]["feasible"],
                    "gaps": jr["estimate"]["gaps"], "est_cents": jr["estimate"]["est_cents"],
                    "ccy": "USD", "basis": jr["estimate"]["basis"],
                    "dispatch_days": None}]
    return _j({"ok": True, "status": "estimated",
               "summary": f"{sum(1 for o in opts if o['feasible'])} feasible lanes for {material} {dims_mm or ''}mm (incl. JLC ROUGH)".strip(),
               "options": opts,
               "next_actions": ["factory_quote for live numbers — Slant/Mixam/Prodigi live, JLC live after approval"]})


async def factory_analyze(model_b64: str, process: str = "WJP_TOUGH",
                        units: str = "mm") -> str:
    """Manufacturability verdicts for a base64 STL/GLB against a JLC process:
    dims, volume, manifold issues + wall/build-volume/detail gates. Local
    compute, no credentials. units: mm for print STLs, m for Blender-native
    exports (Blender scenes export meters by default — pass m). A pass here
    is printability, not proof."""
    try:
        blob = base64.b64decode(model_b64, validate=True)
    except Exception:
        return _j({"status": "needs_input", "summary": "model_b64 is not valid base64",
                   "next_actions": ["send base64 STL (print units mm) or GLB"]})
    if len(blob) > 50_000_000:
        return _j({"status": "needs_input", "summary": "model over 50MB",
                   "next_actions": ["decimate or send a smaller revision"]})
    try:
        report = _geo.mesh_report(blob, units=units)
        if units == "m":
            # compensate geometry.py double-conversion (scales to mm then
            # multiplies volume by 1e6 again); dims are already correct mm.
            report["volume_cm3"] = round(report["volume_cm3"] / 1e6, 2)
    except Exception as e:  # noqa: BLE001
        return _j({"status": "needs_input", "summary": f"unparseable model: {e}",
                   "next_actions": ["send STL/3MF-exported STL or GLB, mm units"]})
    try:
        verdicts = jlc_check(report, process)
    except KeyError:
        verdicts = [f"no wall rule encoded for {process} (constraint-table gap — reported)"]
    return _j({"ok": True, "report": report, "process": process,
               "verdicts": verdicts,
               "summary": ("PASS " + process if not verdicts else "GAPS: " + "; ".join(verdicts)),
               "next_actions": ["factory_estimate for lane pricing", "factory_request_proof (stub) before any order"]})


SLANT_MCP = "https://www.slant3d.com/mcp"
MIXAM_OFFERS = "https://mixam.co.uk/api/public/offers"
MIXAM_META = "https://mixam.co.uk/api/public/products/metadata/{pid}/{sub}"
_UA = {"User-Agent": "Mozilla/5.0 (oddhobb-factory)"}


def _http_json(url: str, body: dict | None = None, timeout: int = 60) -> dict:
    import urllib.request
    data = json.dumps(body).encode() if body is not None else None
    h = dict(_UA)
    h["Accept"] = "application/json, text/event-stream"
    if data is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h,
                                 method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return {"status": r.status, "body": r.read().decode()}


async def _slant_quote_live(model_b64: str, filename: str) -> dict:
    """Keyless live quote via Slant's public MCP (STL units read as mm)."""
    import asyncio as _a

    def work() -> dict:
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "oddhobb-factory", "version": VERSION}}}
        call = {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "quote_upload_part",
                           "arguments": {"file_content": model_b64, "file_name": filename}}}
        _http_json(SLANT_MCP, init)
        out = _http_json(SLANT_MCP, call)["body"]
        payloads = [l[6:] for l in out.split("\n") if l.startswith("data: ")]
        d = json.loads(payloads[-1])
        res = d.get("result", {})
        if res.get("isError"):
            txt = json.dumps(res.get("content", []))
            return {"ok": False, "error": txt[:300]}
        txt = res["content"][0]["text"]
        return {"ok": True, "quote": json.loads(txt)}

    try:
        return await _a.to_thread(work)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"slant unreachable: {e}"}


async def _mixam_quote_live(product_id: int = 10, sub_id: int = 0,
                            copies: int = 25) -> dict:
    """Keyless live quote via Mixam public offers API."""
    import asyncio as _a

    def work() -> dict:
        meta = json.loads(_http_json(MIXAM_META.format(pid=product_id, sub=sub_id))["body"])
        spec = meta["productMetadata"]["initialSpecification"]
        spec["copies"] = copies
        d = json.loads(_http_json(MIXAM_OFFERS, {"subProductId": sub_id,
                                                 "itemSpecification": spec,
                                                 "santaType": "QUOTE"})["body"])
        return {"ok": True, "offers": d.get("offers", []),
                "weight_kg": d.get("weightKg")}

    try:
        return await _a.to_thread(work)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"mixam unreachable: {e}"}


async def _prodigi_quote_live(sku: str, copies: int, country: str) -> dict:
    """Live Prodigi quote (needs PRODIGI_API_KEY env — free, no order)."""
    import asyncio as _a

    def work() -> dict:
        from backend import prodigi as _p
        return {"ok": True, "quote": _p.quote(sku, copies, country)}

    try:
        return await _a.to_thread(work)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"prodigi quotefailed: {e}"}


# Capability truth (verified sources only — never inferred).
# Full-colour photographic: JLC WJP alone. Farm-lane "multicolour" is <=4
# filament colours, not full-colour. Monochrome lanes must never win a
# full-colour job no matter how cheap.
FULLCOLOR_LANES = frozenset({"jlc"})
MONO_LANES = frozenset({"makr3d", "printie", "yorkshire3d", "fdfarm", "slant3d",
                        "dapi3d", "sculpteo", "shapeways", "treatstock",
                        "craftcloud", "xometry"})
FULLCOLOR_NOTES = ("WJP matte finish, 600x1200dpi-class, no metallic, fades "
                   "in sun; walls >=1.0mm (Tough 0.8), emboss >=0.8mm, no "
                   "enclosed hollows — see docs/jlc-materials.md")


async def _decide(requirements: dict, offers: list[dict],
                  estimates: list[dict], unwired: list[str]) -> dict:
    """ONE decision: cheapest landed offer meeting every requirement +
    deadline. Capability gates (full-colour, material) override price —
    a lane that cannot do the job is rejected with its reason, never ranked."""
    fullcolor = bool(requirements.get("full_color"))
    deadline = requirements.get("max_days")
    if fullcolor:
        rejected = [{"lane": o.get("lane"),
                     "reason": "monochrome lane cannot do full-colour"}
                    for o in offers]
        live = []
        jlc_live = [o for o in offers if o.get("lane") in FULLCOLOR_LANES]
        if jlc_live:
            winner = sorted(jlc_live, key=lambda o: o.get("total_gbp") or o.get("subtotal_usd") or 0)[0]
            return {"ok": True, "status": "decided", "decision": winner,
                    "why": "only full-colour-capable lane; " + FULLCOLOR_NOTES,
                    "rejected": rejected, "unwired": unwired}
        return {"ok": True, "status": "needs_input",
                "summary": "no live lane can do full-colour today — refusing to mis-route to monochrome",
                "quality_bar": FULLCOLOR_NOTES,
                "rough_jlc": (sorted([e for e in estimates if e.get("feasible") and e.get("est_cents")],
                                     key=lambda e: e["est_cents"])[0]
                              if any(e.get("feasible") and e.get("est_cents") for e in estimates) else None),
                "rejected": rejected, "unwired": unwired,
                "next_actions": ["human: brick WJP order (builds JLC approval history)",
                                 "human: apply at api.jlcpcb.com for TDP pricing API"]}
    feas = [o for o in offers if o.get("grade") == "LIVE"]
    if deadline is not None:
        in_time = [o for o in feas if (o.get("days") is not None and o.get("days") <= deadline)]
        rejected_dl = [{"lane": o.get("lane"), "reason": f"misses {deadline}-day deadline"}
                       for o in feas if o not in in_time]
    else:
        in_time, rejected_dl = feas, []
    key = lambda o: (o.get("total_gbp") if o.get("total_gbp") is not None
                     else (o.get("subtotal_usd") or 0))
    if in_time:
        winner = sorted(in_time, key=key)[0]
        rejected = rejected_dl + [{"lane": o.get("lane"), "reason": "dearer landed"} for o in in_time if o is not winner]
        return {"ok": True, "status": "decided", "decision": winner,
                "why": f"cheapest landed meeting all requirements{f' and {deadline}-day deadline' if deadline else ''}",
                "rejected": rejected, "unwired": unwired}
    best_est = sorted([e for e in estimates if e.get("feasible") and e.get("est_cents")],
                      key=lambda e: e["est_cents"])
    return {"ok": True, "status": "needs_input",
            "summary": "no live offer meets the brief — best estimate held, nothing ordered",
            "best_estimate": best_est[0] if best_est else None,
            "rejected": rejected_dl, "unwired": unwired,
            "next_actions": ["loosen deadline/budget or wait for lane keys"]}


async def factory_quote(kind: str = "3d", model_b64: str = "",
                       filename: str = "part.stl", copies: int = 1,
                       country: str = "GB", region: str = "US",
                       material: str = "PLA", full_color: bool = False,
                       max_days: int | None = None) -> str:
    """ONE decision, not a menu: cheapest landed offer meeting every requirement.
    full_color=True hard-excludes all monochrome lanes (Slant/farm can never win
    a full-colour job — today that resolves to the JLC path with exact unblocks
    rather than a mis-route). kind=3d needs model_b64 (STL, MILLIMETRES).
    kind=card fans Mixam (live) + Prodigi (live with key)."""
    offers: list[dict] = []
    unwired: list[str] = []
    if kind == "3d":
        if not model_b64:
            return _j({"status": "needs_input", "summary": "kind=3d needs model_b64 (STL, mm units)",
                       "next_actions": ["send base64 STL or run factory_analyze first"]})
        sq = await _slant_quote_live(model_b64, filename)
        if sq.get("ok"):
            import re as _re
            q = sq["quote"]
            for v in q.get("volume_pricing", [])[:3]:
                m = _re.search(r"\d+", v.get("lead_time") or "")
                offers.append({"lane": "slant3d", "grade": "LIVE",
                               "qty": v.get("quantity"), "unit_usd": v.get("unit_price_usd"),
                               "subtotal_usd": v.get("subtotal_usd"),
                               "lead": v.get("lead_time"),
                               "days": int(m.group()) if m else None,
                               "quote_id": q.get("quote_id"),
                               "feedback": [i.get("title") for i in
                                            q.get("print_feedback", {}).get("issues", [])]})
        else:
            unwired.append(f"slant failed: {sq.get('error')} (surface Slant message verbatim)")
        unwired += ["makr3d: local band only — m3d_live_ Bearer key (owner: dashboard Settings → API keys, quotes scope) unlocks live v1 quotes",
                    "jlc: needs pricing-API approval (brick order first, then api.jlcpcb.com)",
                    "treatstock/shapeways/3dapi: free keys via support/signup",
                    "sculpteo: partnership key", "craftcloud: Kiln MCP for machine path"]
        sq_vol = None
        try:
            if sq.get("ok"):
                sq_vol = float(sq["quote"].get("volume_cm3") or 0) or None
        except Exception:  # noqa: BLE001
            sq_vol = None
        jr = _jlc_rough("FULL-COLOR" if full_color else material, sq_vol, None)
        ests = [jr["estimate"]] if jr["estimate"].get("feasible") else []
        return _j(await _decide({"full_color": full_color, "max_days": max_days},
                                offers, ests, unwired))
    if kind == "card":
        mx = await _mixam_quote_live(10, 0, copies)
        if mx.get("ok"):
            for o in mx["offers"][:4]:
                offers.append({"lane": "mixam", "grade": "LIVE",
                               "total_gbp": o.get("price"), "days": o.get("productionDays"),
                               "delivery": (o.get("estimatedDeliveryDate") or {}).get("date"),
                               "best_price": o.get("bestPrice"), "express": o.get("express"),
                               "ex_shipping": not o.get("includeShipment")})
        else:
            unwired.append(f"mixam failed: {mx.get('error')}")
        pq = await _prodigi_quote_live("CLASSIC-GRE-FEDR-7X5-BLA", copies, country)
        if pq.get("ok") and isinstance(pq.get("quote"), dict) and pq["quote"].get("ok"):
            q = pq["quote"]
            offers.append({"lane": "prodigi", "grade": "LIVE", "total_gbp": q.get("total"),
                           "item": q.get("item"), "shipping": q.get("shipping"),
                           "tax": q.get("tax"), "carrier": q.get("carrier")})
        else:
            unwired.append(f"prodigi card: {pq.get('error', pq.get('quote'))} (canvas SKU verified live separately)")
        unwired += ["gelato/printify: owner signup for X-API-KEY / account (no keys stored)"]
        return _j(await _decide({"full_color": False, "max_days": max_days},
                                offers, [], unwired))
    return _j({"status": "needs_input", "summary": f"unknown kind {kind!r}",
               "next_actions": ["kind=3d (with model_b64) or kind=card"]})


async def factory_compare(note: str = "") -> str:
    """Ranked quoted offers (STUB): needs factory_quote live first."""
    _ = note
    return _j({"status": "needs_input", "summary": "compare needs quoted offers — quote tier not live",
               "next_actions": ["factory_estimate for estimated ranking"]})


async def factory_request_proof(note: str = "") -> str:
    """Production proof before money moves (STUB): render/photo approval step.
    Even a printable file can be wrong (textures, orientation, faces)."""
    _ = note
    return _j({"status": "needs_input", "summary": "proof flow not built — Phase 2",
               "next_actions": ["factory_analyze for geometry verdicts now"]})


async def factory_order_prepare(note: str = "") -> str:
    """Pinned order draft (STUB): file-hash + quote-expiry + address routing.
    Preparing never spends; confirming does (and is off)."""
    _ = note
    return _j({"status": "needs_input", "summary": "ordering not live — approval + FACTORY_ENABLE_ORDERS gate",
               "next_actions": ["factory_quote (stub) for the path", "human approval required before any confirm"]})


async def factory_order_confirm(note: str = "") -> str:
    """Commit a prepared order (STUB, default-off)."""
    _ = note
    if not ORDERS_ON:
        return _j({"status": "needs_input", "summary": "order placement disabled (FACTORY_ENABLE_ORDERS unset)",
                   "next_actions": ["human: set FACTORY_ENABLE_ORDERS=1 and approve the specific prepared order"]})
    return _j({"status": "needs_input", "summary": "no prepared orders exist yet — prepare first",
               "next_actions": ["factory_order_prepare"]})


async def factory_track(batch: str = "") -> str:
    """Production + shipping status by batch (STUB until ordering live)."""
    _ = batch
    return _j({"status": "needs_input", "summary": "tracking needs live orders",
               "next_actions": ["factory_order_prepare for the path"]})


TOOL_AREAS = {
    "library": [factory_tools],
    "reference": [factory_catalog, factory_suppliers],
    "design": [factory_analyze, factory_estimate],
    "buy": [factory_quote, factory_compare, factory_request_proof,
            factory_order_prepare, factory_order_confirm, factory_track],
}

PUBLIC_TOOLS = frozenset({
    "factory_tools",
    "factory_catalog",
    "factory_suppliers",
    "factory_estimate",
    "factory_analyze",
    "factory_quote",
})

if os.environ.get("PUBLIC_MCP") == "1":
    TOOL_AREAS = {a: [fn for fn in fns if fn.__name__ in PUBLIC_TOOLS]
                  for a, fns in TOOL_AREAS.items()}
    TOOL_AREAS = {a: fns for a, fns in TOOL_AREAS.items() if fns}

for _fns in list(TOOL_AREAS.values()):
    for _fn in _fns:
        mcp.tool()(_fn)


async def main() -> None:
    if os.environ.get("MCP_HTTP"):
        print(f"factory MCP (streamable http) on http://127.0.0.1:{PORT}/mcp", file=sys.stderr)
        await mcp.run_streamable_http_async(host="127.0.0.1", port=PORT)
    else:
        await mcp.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
