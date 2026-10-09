import trimesh, numpy as np, sys
for k in ['pyjama','dress']:
    m=trimesh.load(f'prod/brick-figure-{k}-production.stl')
    H=m.bounds[1]-m.bounds[0]; print(k,'faces',len(m.faces),'extent',H.round(3))
    bodies=m.split(only_watertight=False)
    for i,b in enumerate(bodies):
        print(f'  body{i} faces={len(b.faces)} watertight={b.is_watertight} winding={b.is_winding_consistent} volume={b.volume:.4f} euler={b.euler_number}')
