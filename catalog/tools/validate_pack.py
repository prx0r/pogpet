#!/usr/bin/env python3
"""OddHobb pack gate runner. Deterministic: same files in -> same verdict out.

  python3 tools/validate_pack.py packs/<SKU> [packs/<SKU> ...] [--preflight] [--quiet]
  python3 tools/validate_pack.py --all [--preflight]

--preflight re-runs pipeline/preflight.py on the pack's print file and writes print/preflight.json
(stamped with the print file's sha256). Without it the existing report is checked.
Writes <pack>/gates.json (never hand-edit) and prints one line per gate.
Exit code: 0 if every pack reached LISTABLE, 1 otherwise.
"""
import sys, os, json, hashlib, subprocess, datetime, re
from PIL import Image
from jsonschema import Draft202012Validator

CAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(CAT)
CFG = json.load(open(f'{CAT}/config.json'))
SUP = json.load(open(f'{CAT}/suppliers.json'))
SCHEMA = json.load(open(f'{CAT}/schema/pack.schema.json'))
PREFLIGHT = f'{ROOT}/pipeline/preflight.py'
TODAY = datetime.date.today()


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def pj(pack, rel):
    return None if rel is None else (rel if os.path.isabs(rel) else os.path.join(pack, rel))


def run(pack, do_preflight=False):
    G = {}
    def gate(gid, name, ok, why=''):
        G[gid] = dict(name=name, status='PASS' if ok else 'FAIL', why=why if not ok else '')
    def fail_all(ids, why):
        for i, n in ids: gate(i, n, False, why)

    sku = os.path.basename(os.path.normpath(pack))
    pfile = f'{pack}/product.json'
    # G01 structure + schema
    try:
        P = json.load(open(pfile))
    except Exception as e:
        gate('G01', 'structure + schema', False, f'product.json unreadable: {e}')
        return finish(pack, sku, G, None)
    errs = [f'{"/".join(map(str, e.path)) or "(root)"}: {e.message}' for e in Draft202012Validator(SCHEMA).iter_errors(P)]
    missing = [d for d in ('print', 'listing') if not os.path.isdir(f'{pack}/{d}')]
    probs = errs[:6] + ([f'sku {P.get("sku")} != folder {sku}'] if P.get('sku') != sku else []) + [f'missing dir {d}/' for d in missing]
    gate('G01', 'structure + schema', not probs, '; '.join(probs))
    if errs:
        return finish(pack, sku, G, P)
    M, C, L = P['manufacture'], P['cost'], P['listing']
    proc = CFG['processes'].get(M['process'])

    # G02 supplier + process known
    s = SUP.get(M['supplier'])
    why = []
    if not s: why.append(f'supplier {M["supplier"]} not in suppliers.json')
    if not proc: why.append(f'process {M["process"]} not in config.processes')
    if s and M['process'] not in s['processes']: why.append(f'{M["supplier"]} does not offer {M["process"]}')
    gate('G02', 'supplier + process known', not why, '; '.join(why))

    # G03 print file exists, sha pinned, right format for the process
    pf = M['print_file']; ppath = pj(pack, pf['path']); why = []
    psha = None
    if not pf['path'] or not os.path.isfile(ppath): why.append('no print file')
    else:
        psha = sha(ppath)
        if pf['sha256'] != psha: why.append(f'sha256 mismatch (file {psha[:12]} vs json {str(pf["sha256"])[:12]})')
        if not ppath.startswith(os.path.abspath(pack) + '/print/') and not os.path.abspath(ppath).startswith(os.path.abspath(pack) + '/print/'):
            why.append('print file must live inside the pack under print/')
        if proc and pf['format'] != proc['print_format']: why.append(f'format {pf["format"]} but {M["process"]} needs {proc["print_format"]}')
    gate('G03', 'print file present + pinned', not why, '; '.join(why))

    # G04 preflight on that exact file, all warnings acknowledged
    rep = pj(pack, M['preflight']['report']) or f'{pack}/print/preflight.json'
    why = []
    if proc and proc['preflight'] is None:
        why.append(f'no automated preflight exists for {M["process"]} yet (needs a supplier DFM check recorded by hand in evidence/)')
        dfm = f'{pack}/evidence/dfm.json'
        if os.path.isfile(dfm):
            d = json.load(open(dfm)); why = [] if d.get('print_sha256') == psha and d.get('verdict') == 'PASS' else ['evidence/dfm.json not PASS for this print sha']
    elif psha:
        if do_preflight:
            rep = f'{pack}/print/preflight.json'
            r = subprocess.run([sys.executable, PREFLIGHT, ppath, '--process', proc['preflight'], '--json', rep] +
                               (['--prep', f'{pack}/print/prep_report.json'] if os.path.isfile(f'{pack}/print/prep_report.json') else []),
                               capture_output=True, text=True)
            if os.path.isfile(rep):
                d = json.load(open(rep)); d['print_sha256'] = psha; d['ran_at'] = datetime.datetime.now().isoformat(timespec='seconds'); json.dump(d, open(rep, 'w'), indent=1)
            else:
                why.append('preflight crashed: ' + (r.stderr.strip().splitlines() or ['?'])[-1][:160])
        if not why:
            if not os.path.isfile(rep): why.append('no preflight report (run with --preflight)')
            else:
                d = json.load(open(rep))
                if d.get('print_sha256') != psha: why.append('preflight report is for a different file (sha mismatch); re-run --preflight')
                if d.get('verdict') == 'FAIL': why.append('preflight FAIL: ' + ', '.join(c['check'] for c in d['checks'] if c['status'] == 'FAIL'))
                ack = M['preflight']['acknowledged']
                un = [c['check'] for c in d.get('checks', []) if c['status'] == 'WARN' and c['check'] not in ack]
                if un: why.append('unacknowledged warnings: ' + ', '.join(un))
    else:
        why.append('nothing to preflight')
    gate('G04', 'preflight PASS on exact file', not why, '; '.join(why))

    # G05 geometry in product.json agrees with what preflight measured
    why = []
    g = P['geometry']
    if os.path.isfile(rep) and psha:
        d = json.load(open(rep))
        if d.get('print_sha256') == psha:
            md, gd = sorted(d.get('dims_mm') or []), sorted(g['dims_mm'] or [])
            if len(md) != 3 or len(gd) != 3 or any(abs(a - b) > 0.5 for a, b in zip(md, gd)): why.append(f'dims_mm {g["dims_mm"]} vs measured {d.get("dims_mm")}')
            mv = d.get('volume_cm3')
            if mv and (not g['volume_cm3'] or abs(mv - g['volume_cm3']) / mv > 0.02): why.append(f'volume {g["volume_cm3"]} vs measured {mv}')
        else: why.append('no measurement for this print file')
    elif proc and proc['preflight'] is None and g['dims_mm'] and g['volume_cm3']:
        pass
    else: why.append('no measurement to compare (G04 first)')
    gate('G05', 'geometry matches measurement', not why, '; '.join(why))

    # G06 manufacture spec complete + drop-shippable
    why = [k for k in ('material', 'finish', 'colour') if not M.get(k)]
    why = [f'{k} missing' for k in why]
    if M['fulfilment'] == 'dropship' and M['hand_finish']: why.append('hand finish needed but fulfilment is dropship: ' + '; '.join(M['hand_finish']))
    lt = M['lead_time_days']
    if not all(isinstance(lt.get(k), (int, float)) for k in ('build', 'ship_min', 'ship_max')): why.append('lead times missing')
    gate('G06', 'manufacture spec complete', not why, '; '.join(why))

    # G07 real cost: supplier quote or invoice, fresh
    why = []
    for k in ('print', 'shipping'):
        c = C[k]
        if c.get('amount') is None: why.append(f'{k} cost missing'); continue
        if c.get('basis') not in ('quote', 'invoice'): why.append(f'{k} cost is {c.get("basis")}, need a supplier quote')
        try:
            age = (TODAY - datetime.date.fromisoformat(c.get('date') or '')).days
            if age > CFG['quote_max_age_days']: why.append(f'{k} quote {age} days old')
        except ValueError: why.append(f'{k} quote has no ISO date')
        if c.get('basis') in ('quote', 'invoice') and not c.get('ref'): why.append(f'{k} quote has no ref')
    gate('G07', 'real supplier cost', not why, '; '.join(why))

    # G08 margin per channel
    why = []
    price = L['price']['amount']
    if not price: why.append('no price')
    elif not why and C['print'].get('amount') is not None and C['shipping'].get('amount') is not None:
        cost_gbp = (C['print']['amount'] + C['shipping']['amount'] + ((C.get('packaging') or {}).get('amount') or 0)) / CFG['fx']['GBP_USD']
        for ch in L['channels']:
            f = CFG['fees'][ch]
            fee = f.get('listing_gbp', 0) + price * (f.get('transaction_pct', 0) + f.get('payment_pct', 0) + f.get('offsite_ads_pct', 0)) / 100 + f.get('payment_fixed_gbp', 0)
            m = (price - fee - cost_gbp) / price * 100
            if m < CFG['margin_min_pct']: why.append(f'{ch} margin {m:.0f}% < {CFG["margin_min_pct"]}% (price £{price:.2f}, cost £{cost_gbp:.2f}, fees £{fee:.2f})')
    else: why.append('costs missing')
    gate('G08', f'margin >= {CFG["margin_min_pct"]}% per channel', not why, '; '.join(why))

    # G09 personalisation slots
    why = []
    offered = [s for s in P['slots'] if s['offered']]
    if P['kind'] == 'personalised' and not offered: why.append('personalised product offers no slot')
    for s in offered:
        if not s['validated']: why.append(f'slot {s["id"]} offered but not validated against real geometry'); continue
        ev = s.get('evidence')
        if not ev or not (os.path.exists(pj(pack, ev)) or os.path.exists(os.path.join(ROOT, ev))):
            why.append(f'slot {s["id"]} evidence file missing')
        if s['type'] == 'text':
            t = s.get('text', {})
            for k in ('max_chars', 'cap_mm', 'min_cap_mm', 'charset', 'fit'):
                if t.get(k) in (None, ''): why.append(f'slot {s["id"]} text.{k} missing')
            if proc and t.get('min_cap_mm') is not None and t['min_cap_mm'] < proc['min_text_cap_mm']: why.append(f'slot {s["id"]} min_cap {t["min_cap_mm"]} mm < process min {proc["min_text_cap_mm"]}')
            if t.get('fit') and 'error' not in t['fit']: why.append(f'slot {s["id"]} fit policy must end in a hard error (never truncate)')
        if s['type'] == 'colour':
            c = s.get('colour', {}); pal = c.get('palette') or []
            if not pal or c.get('default') not in pal: why.append(f'slot {s["id"]} palette/default invalid')
    gate('G09', 'slots offered are validated', not why, '; '.join(why))

    # G10 listing copy
    lc = CFG['listing']; why = []
    if not L['title'] or len(L['title']) > lc['title_max']: why.append(f'title length {len(L["title"])}')
    if len(L['tags']) != lc['tags_exact'] or len(set(t.lower() for t in L['tags'])) != len(L['tags']): why.append(f'{len(L["tags"])} tags (need {lc["tags_exact"]} unique)')
    long = [t for t in L['tags'] if len(t) > lc['tag_max']]
    if long: why.append(f'tags over {lc["tag_max"]} chars: {long}')
    if not L['materials'] or len(L['materials']) > lc['materials_max']: why.append('materials')
    if len(L['description']) < lc['desc_min']: why.append(f'description {len(L["description"])} chars < {lc["desc_min"]}')
    if len(L['spec_rows']) < lc['spec_rows_min']: why.append('spec rows')
    if not L['processing']: why.append('processing time')
    if not L['channels']: why.append('no channels')
    gate('G10', 'listing copy complete', not why, '; '.join(why))

    # G11 listing images: PNG, big enough, declared, rendered from the exact print file
    why = []
    imgs = L['images']
    if len(imgs) < lc['min_images']: why.append(f'{len(imgs)} images < {lc["min_images"]}')
    if not any(i['role'] == 'hero' for i in imgs): why.append('no hero image')
    man = f'{pack}/listing/renders.json'
    R = json.load(open(man)) if os.path.isfile(man) else None
    if R is None: why.append('listing/renders.json missing (provenance)')
    elif psha and R.get('print_sha256') != psha: why.append('renders were not made from the current print file')
    for i in imgs:
        p = f'{pack}/listing/{i["file"]}'
        if not os.path.isfile(p): why.append(f'{i["file"]} missing'); continue
        if not p.lower().endswith('.png'): why.append(f'{i["file"]} not PNG')
        w, h = Image.open(p).size
        if min(w, h) < lc['min_side_px']: why.append(f'{i["file"]} {w}x{h} < {lc["min_side_px"]}px')
        if R is not None:
            e = (R.get('images') or {}).get(i['file'])
            if not e: why.append(f'{i["file"]} not in renders.json')
            elif e.get('sha256') != sha(p): why.append(f'{i["file"]} changed after render')
        if not i['alt']: why.append(f'{i["file"]} no alt text')
    gate('G11', 'listing images from print file', not why, '; '.join(why[:8]) + (f' (+{len(why) - 8} more)' if len(why) > 8 else ''))

    # G12 audience
    A = P['audience']; why = []
    if len(A['suits']) < 3: why.append('suits < 3')
    if len(A['occasions']) < 2: why.append('occasions < 2')
    if len(A['relationship_to_buyer']) < 1: why.append('no buyer relationship')
    if len(A['not_for']) < 1: why.append('no not_for')
    gate('G12', 'audience defined', not why, '; '.join(why))

    # G13 graph refs resolve
    packs = set(os.listdir(f'{CAT}/packs'))
    refs = P['parents'] + [r['sku'] for r in P['graph'].get('related', [])]
    bad = [r for r in refs if r not in packs and r not in CFG['templates']]
    gate('G13', 'graph refs resolve', not bad, 'unknown refs: ' + ', '.join(bad))

    # G14 physical sample proven
    sm = [s for s in P.get('samples', []) if s.get('verdict') == 'PASS' and os.path.isfile(pj(pack, s['photo']))]
    gate('G14', 'physical sample received + passed', bool(sm), 'no passed sample with photo in samples/')
    return finish(pack, sku, G, P, psha)


def finish(pack, sku, G, P, psha=None):
    order = ['PRINT_READY', 'LISTABLE', 'PROVEN']
    level = 'DRAFT'
    for lv in order:
        if all(G.get(g, {}).get('status') == 'PASS' for g in CFG['levels'][lv]): level = lv
        else: break
    out = dict(sku=sku, level=level, print_sha256=psha, checked_at=datetime.datetime.now().isoformat(timespec='seconds'),
               validator='catalog/tools/validate_pack.py v1', gates=G)
    json.dump(out, open(f'{pack}/gates.json', 'w'), indent=1)
    return out


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if '--all' in sys.argv: a = sorted(f'{CAT}/packs/{d}' for d in os.listdir(f'{CAT}/packs') if os.path.isdir(f'{CAT}/packs/{d}'))
    allok = True
    for p in a:
        o = run(os.path.abspath(p), '--preflight' in sys.argv)
        allok &= o['level'] in ('LISTABLE', 'PROVEN')
        print(f'\n== {o["sku"]}: {o["level"]}')
        if '--quiet' not in sys.argv:
            for k in sorted(o['gates']):
                g = o['gates'][k]; print(f'  {k} {g["status"]:4} {g["name"]}' + (f'  -> {g["why"]}' if g['why'] else ''))
    sys.exit(0 if allok else 1)
