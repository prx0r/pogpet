exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/geo.py').read())
# prop: walnut cribbage board 300 x 80 x 18, 3 tracks, holes 3.2 mm, groups of 5
board = rounded_box(300, 84, 18, r=3)
holes = []; HP = []
for t, y in enumerate([-12, 0, 12]):
    for g in range(6):
        for k in range(5):
            x = -125 + g * 44 + k * 6.35
            holes.append(cyl(1.6, 16, x, y, 4, n=24)); HP.append((x, y))
inl = CS()
for g in range(7): inl = inl + rect(0.8, 40, -132 + g * 44 - 3.3, 0)
board = board - union(holes)
save({'board': board, 'inlay': ext(inl, 0.2, 17.9)}, 'p05_board')
import json; json.dump(HP, open(OUT + 'p05_board/holes.json', 'w'))
