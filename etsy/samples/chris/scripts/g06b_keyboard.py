exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/geo.py').read())
H = 8.4
def blank(w=1):
    W = 18.0 + (w - 1) * 19.05
    return M.batch_hull([ext(rect(W, 18.0, r=1.8), 0.01, 0), ext(rect(W - 4.8, 12.6, 0, 0.6, r=2.6), 0.01, H)])
caps = []; hero = None
rows = [[1] * 7, [1.25] + [1] * 6, [1.75] + [1] * 5, [2.25] + [1] * 4]
for r, row in enumerate(rows):
    x = -70.0 + r * 4.0
    for i, w in enumerate(row):
        W = w * 19.05; cx = x + W / 2
        if r == 1 and i == 3: hero = (cx, -r * 19.05)
        else: caps.append(blank(w).translate((cx, -r * 19.05, 0)))
        x += W
plate = rounded_box(150, 92, 6, r=1.2, x=-6, y=-28.6, z=-10)
save({'caps': union(caps), 'plate': plate}, 'p06_keyboard')
import json; json.dump(hero, open(OUT + 'p06_keyboard/hero.json', 'w'))
