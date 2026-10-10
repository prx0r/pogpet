"""OddHobb JLC preflight: the final gate before anything is uploaded to JLC3DP.
python3 preflight.py <jlc.zip> --process wjp --target-h 80 [--prep prep_report.json] [--json out.json]
Exit code 0 = PASS (warnings allowed), 1 = FAIL. Every check prints PASS/WARN/FAIL with its measured value.
Rules come from our proven brick-figure run (docs/brick-figure-production-guide.md) + RULES below (edit, don't hardcode elsewhere).
"""
import sys, os, json, zipfile, tempfile, argparse, re
import numpy as np, trimesh
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

RULES = {
    'wjp': dict(max_zip_mb=12.0, min_tex=2048, max_tex=8192, min_wall_mm=0.8, max_dims_mm=(250, 250, 200),
                need_texture=True, cost_per_cm3=0.82, cost_floor=6.91, max_faces=1_000_000),
    'mjf': dict(max_zip_mb=50.0, min_tex=0, max_tex=0, min_wall_mm=1.0, max_dims_mm=(380, 284, 380),
                need_texture=False, cost_per_cm3=0.35, cost_floor=3.0, max_faces=2_000_000),
    'sla': dict(max_zip_mb=50.0, min_tex=0, max_tex=0, min_wall_mm=0.8, max_dims_mm=(250, 250, 250),
                need_texture=False, cost_per_cm3=0.25, cost_floor=1.0, max_faces=2_000_000),
}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('zip'); ap.add_argument('--process', default='wjp')
    ap.add_argument('--target-h', type=float); ap.add_argument('--prep'); ap.add_argument('--json')
    a = ap.parse_args(); R = RULES[a.process]; res = []
    def chk(name, status, value, note=''):
        res.append(dict(check=name, status=status, value=value, note=note)); print(f'{status:4}  {name:28} {value}  {note}')
    zmb = os.path.getsize(a.zip) / 1e6
    chk('zip size', 'PASS' if zmb <= 8 else ('WARN' if zmb <= R['max_zip_mb'] else 'FAIL'), f'{zmb:.1f} MB', f'limit {R["max_zip_mb"]} MB (6-7 MB proven, 14-16 MB failed)')
    d = tempfile.mkdtemp(); z = zipfile.ZipFile(a.zip); names = z.namelist(); z.extractall(d)
    flat = all('/' not in n for n in names)
    chk('zip flat (files at root)', 'PASS' if flat else 'FAIL', names)
    objs = [n for n in names if n.lower().endswith('.obj')]; mtls = [n for n in names if n.lower().endswith('.mtl')]
    chk('one OBJ', 'PASS' if len(objs) == 1 else 'FAIL', objs)
    texs = []
    if R['need_texture']:
        if not mtls: chk('MTL present', 'FAIL', 'none')
        else:
            mt = open(os.path.join(d, mtls[0])).read()
            kd = re.findall(r'^Kd\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)', mt, re.M)
            ok = kd and all(abs(float(x) - 1.0) < 1e-3 for x in kd[0])
            chk('MTL Kd = 1.0 (else prints dark)', 'PASS' if ok else 'FAIL', kd)
            texs = re.findall(r'^map_Kd\s+(.+)$', mt, re.M)
            exists = texs and os.path.exists(os.path.join(d, texs[0].strip()))
            chk('map_Kd texture linked', 'PASS' if exists else 'FAIL', texs)
            if exists:
                im = Image.open(os.path.join(d, texs[0].strip())); w, h = im.size
                st = 'PASS' if R['min_tex'] <= max(w, h) <= R['max_tex'] else 'WARN'
                chk('texture size', st, f'{w}x{h} {im.mode}', f'{R["min_tex"]}-{R["max_tex"]}')
        objtxt_has_vt = False
        with open(os.path.join(d, objs[0])) as f:
            for i, line in enumerate(f):
                if line.startswith('vt '): objtxt_has_vt = True; break
                if i > 5_000_000: break
        chk('OBJ has UVs (vt)', 'PASS' if objtxt_has_vt else 'FAIL', objtxt_has_vt)
    m = trimesh.load(os.path.join(d, objs[0]), process=False, force='mesh')
    ext = m.extents
    chk('face count', 'PASS' if len(m.faces) <= R['max_faces'] else 'WARN', len(m.faces))
    fits = all(e <= l for e, l in zip(sorted(ext, reverse=True), sorted(R['max_dims_mm'], reverse=True)))
    chk('dimensions (OBJ units = mm)', 'PASS' if fits and ext.max() > 5 else 'FAIL', [round(x, 2) for x in ext], 'JLC reads OBJ numbers as mm')
    if a.target_h:
        hz = ext[2]; chk('height = target', 'PASS' if abs(hz - a.target_h) < 0.5 else 'FAIL', f'{hz:.2f} vs {a.target_h}')
    zmin = m.vertices[:, 2].min(); base = m.vertices[m.vertices[:, 2] < zmin + 0.3]
    if len(base) > 3:
        foot = np.ptp(base[:, :2], axis=0)
        chk('stands flat (contact patch)', 'PASS' if min(foot[:2]) > 0.15 * min(ext[:2]) else 'WARN', f'{foot[0]:.1f} x {foot[1]:.1f} mm at z=0')
    w = trimesh.Trimesh(np.round(m.vertices, 4), m.faces, process=True)
    e = np.sort(w.edges, axis=1); _, c = np.unique(e, axis=0, return_counts=True)
    op, nm = int((c == 1).sum()), int((c > 2).sum())
    chk('open edges (welded)', 'PASS' if op == 0 else 'FAIL', op)
    chk('non-manifold edges (welded)', 'PASS' if nm == 0 else ('WARN' if nm < 20 else 'FAIL'), nm, 'WJP tolerates a few; JLC reviewer may query')
    chk('watertight', 'PASS' if w.is_watertight else 'FAIL', w.is_watertight)
    chk('winding consistent', 'PASS' if w.is_winding_consistent else 'WARN', w.is_winding_consistent)
    shells = w.split(only_watertight=False); big = [s for s in shells if len(s.faces) > 0.002 * len(w.faces)]
    chk('shells (no floaters)', 'PASS' if len(shells) == len(big) else 'FAIL', f'{len(shells)} shells, {len(shells) - len(big)} debris')
    vol = abs(w.volume) / 1000 if w.is_watertight else float('nan')
    chk('resin volume', 'PASS' if w.is_watertight else 'WARN', f'{vol:.1f} cm3')
    if a.prep and os.path.exists(a.prep):
        P = json.load(open(a.prep)); af = P.get('after_fix', {})
        thin = af.get('Thin Faces', af.get('Thickness', 'n/a'))
        try: tn = int(str(thin).split()[0])
        except Exception: tn = -1
        chk(f'thin walls < {R["min_wall_mm"]} mm', 'PASS' if tn == 0 else 'WARN', thin, 'JLC flags thin walls on every figure; tick the risk box, check limbs/ears/tails')
        inter = af.get('Intersect Face', af.get('Intersect Faces', 'n/a'))
        chk('self-intersections', 'PASS' if str(inter).startswith('0') else 'WARN', inter, 'overlapping shells fuse in WJP')
    est = max(R['cost_floor'], vol * R['cost_per_cm3']) if vol == vol else None
    chk('cost estimate (JLC, qty 1)', 'INFO', f'${est:.2f}' if est else 'n/a', f'~${R["cost_per_cm3"]}/cm3, floor ${R["cost_floor"]}; quote is final')
    fails = [r for r in res if r['status'] == 'FAIL']; warns = [r for r in res if r['status'] == 'WARN']
    verdict = 'FAIL' if fails else ('PASS_WITH_WARNINGS' if warns else 'PASS')
    print('VERDICT', verdict)
    out = dict(zip=os.path.basename(a.zip), process=a.process, verdict=verdict, volume_cm3=round(vol, 2) if vol == vol else None,
               cost_estimate_usd=round(est, 2) if est else None, dims_mm=[round(x, 2) for x in ext], checks=res)
    if a.json: json.dump(out, open(a.json, 'w'), indent=1)
    sys.exit(1 if fails else 0)

if __name__ == '__main__': main()
