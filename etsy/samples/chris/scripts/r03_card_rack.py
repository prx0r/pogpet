import sys; exec(open('/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/studio.py').read())
reset()
P = 'p03_card_rack'
rk = load_part(P, 'rack', mjf_pa12('#26272b'), 30)
fl = load_part(P, 'fill', mat('gold', hexc('#d7b25a'), rough=0.3, metal=1.0), 30)
sw = backdrop('#d9cbb4', size=1800, curve=320); sw.location = (0, 120, 0)
tiers = [(-14.25, 4, ['card_10H', 'card_JH', 'card_QH', 'card_KH', 'card_AH']),
         (0.75, 10, ['card_5C', 'card_7C', 'card_9C', 'card_JC', 'card_KC']),
         (15.75, 18, ['card_7D', 'card_AD', 'card_JS', 'card_QS', 'card_AS'])]
for ti, (gy, gz, cards) in enumerate(tiers):
    n = len(cards); span = 27
    for i, c in enumerate(cards):
        x = (i - (n - 1) / 2) * span
        play_card(c, x + ti * 6, gy + 1.3 - i * 0.32, gz + 0.2, lean=10)
# a few loose cards + score pad on table
world(0.3, '#fff4e6')
light_area((-300, -300, 420), size=380, energy=6.5e5, color=(1, .95, .87))
light_area((340, -120, 200), size=240, energy=1.6e5, color=(.9, .95, 1))
light_area((0, 300, 380), size=320, energy=2.4e5)
cam = Vector((-110, -265, 245))
camera(cam, (0, 6, 34), lens=55, fstop=10, focus=(cam - Vector((0, -31, 6))).length)
go(P)
