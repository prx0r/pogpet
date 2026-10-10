"""UV-preserving watertight repair for textured OBJs (generalised from bricks/jlc/repair2.py).
python3 repair_uv.py <in.obj> <out.obj>
1) weld positions (5 dp) for topology, keep per-corner UVs
2) drop debris shells (<0.2% of faces)
3) drop flap faces whose 3 edges are all non-manifold/open, and faces on >2-face edges (then refill)
4) close every boundary loop with a centroid fan (UV = UV of nearest loop corner, so no seam smearing)
5) repeat up to 4 passes, report open / non-manifold counts."""
import sys, numpy as np
from collections import defaultdict
src, dst = sys.argv[1], sys.argv[2]
V, VT, F, FT = [], [], [], []
for line in open(src):
    if line.startswith('v '): V.append([float(x) for x in line.split()[1:4]])
    elif line.startswith('vt '): VT.append([float(x) for x in line.split()[1:3]])
    elif line.startswith('f '):
        c = [p.split('/') for p in line.split()[1:]]
        for i in range(1, len(c) - 1):
            tri = [c[0], c[i], c[i + 1]]
            F.append([int(t[0]) - 1 for t in tri]); FT.append([int(t[1]) - 1 for t in tri])
V, VT, F, FT = np.array(V), np.array(VT), np.array(F), np.array(FT)
_, inv = np.unique(np.round(V, 5), axis=0, return_inverse=True); inv = inv.ravel()
Fw = inv[F]
Vw = np.zeros((inv.max() + 1, 3)); Vw[inv] = V
def emap(Fw):
    d = defaultdict(list)
    for fi, f in enumerate(Fw):
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])): d[(min(a, b), max(a, b))].append(fi)
    return d
def stats(Fw):
    d = emap(Fw); c = np.array([len(v) for v in d.values()]); return int((c == 1).sum()), int((c > 2).sum()), d
def shells(Fw):
    d = emap(Fw); adj = defaultdict(list)
    for fs in d.values():
        for i in fs:
            for j in fs:
                if i != j: adj[i].append(j)
    lab = -np.ones(len(Fw), int); k = 0
    for s in range(len(Fw)):
        if lab[s] >= 0: continue
        st = [s]; lab[s] = k
        while st:
            x = st.pop()
            for y in adj[x]:
                if lab[y] < 0: lab[y] = k; st.append(y)
        k += 1
    return lab
lab = shells(Fw); cnt = np.bincount(lab); keep = cnt[lab] >= 0.002 * len(Fw)
print('debris shells', int((cnt < 0.002 * len(Fw)).sum()), 'faces', int((~keep).sum()))
Fw, FT = Fw[keep], FT[keep]
# remove degenerate
nd = (Fw[:, 0] != Fw[:, 1]) & (Fw[:, 1] != Fw[:, 2]) & (Fw[:, 0] != Fw[:, 2]); Fw, FT = Fw[nd], FT[nd]
VT = list(map(list, VT)); Vw = list(map(list, Vw))
for it in range(4):
    op, nm, d = stats(Fw); print(f'pass {it}: open {op} nonmanifold {nm}')
    if op == 0 and nm == 0: break
    bad = {k for k, v in d.items() if len(v) > 2}
    drop = set()
    for k in bad:
        drop.update(d[k])  # remove all faces touching a >2 edge; fan refill closes them
    for k, v in d.items():
        if len(v) == 1:
            f = Fw[v[0]]; es = [(min(a, b), max(a, b)) for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0]))]
            if all(len(d[e]) != 2 for e in es): drop.add(v[0])
    if drop:
        m = np.ones(len(Fw), bool); m[list(drop)] = False; Fw, FT = Fw[m], FT[m]
    # also drop faces that now hang by a single edge repeatedly? handled by next pass
    op, nm, d = stats(Fw)
    # boundary half-edges with orientation and the UV at each corner
    nxt = {}; uvat = {}
    for fi, f in enumerate(Fw):
        for j in range(3):
            a, b = f[j], f[(j + 1) % 3]
            if len(d[(min(a, b), max(a, b))]) == 1:
                nxt.setdefault(b, []).append(a)  # fill goes reverse: b -> a
                uvat[a] = FT[fi][j]; uvat[b] = FT[fi][(j + 1) % 3]
    newF, newT = [], []
    used = set()
    for s in list(nxt.keys()):
        if s in used or not nxt.get(s): continue
        loop = [s]; cur = s; ok = False
        for _ in range(100000):
            if not nxt.get(cur): break
            n = nxt[cur].pop()
            if n == s: ok = True; break
            if n in loop: break
            loop.append(n); cur = n
        used.update(loop)
        if not ok or len(loop) < 3: continue
        P = np.array([Vw[i] for i in loop]); c = P.mean(0)
        ci = len(Vw); Vw.append(list(c))
        near = loop[int(np.argmin(((P - c) ** 2).sum(1)))]
        cu = uvat.get(near, 0)
        for i in range(len(loop)):
            a, b = loop[i], loop[(i + 1) % len(loop)]
            newF.append([a, b, ci]); newT.append([uvat.get(a, cu), uvat.get(b, cu), cu])
    if newF:
        Fw = np.vstack([Fw, np.array(newF)]); FT = np.vstack([FT, np.array(newT)])
    print(f'  filled {len(newF)} tris')
op, nm, _ = stats(Fw); print('FINAL open', op, 'nonmanifold', nm)
used_v = np.unique(Fw); remap = -np.ones(len(Vw), int); remap[used_v] = np.arange(len(used_v))
used_t = np.unique(FT); rt = -np.ones(len(VT), int); rt[used_t] = np.arange(len(used_t))
Vw = np.array(Vw); VT = np.array(VT)
with open(dst, 'w') as o:
    o.write('mtllib model.mtl\nusemtl m\n')
    o.write(''.join(f'v {x:.4f} {y:.4f} {z:.4f}\n' for x, y, z in Vw[used_v]))
    o.write(''.join(f'vt {u:.5f} {v:.5f}\n' for u, v in VT[used_t]))
    F2 = remap[Fw] + 1; T2 = rt[FT] + 1
    o.write(''.join(f'f {a}/{p} {b}/{q} {c}/{r}\n' for (a, b, c), (p, q, r) in zip(F2, T2)))
print('WROTE', dst)
