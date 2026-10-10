#!/usr/bin/env python3
"""One-off (2026-10-10): build packs for every product made so far from the existing work folders.
Honest import: nothing is marked validated/quoted unless it actually was. Re-runnable (overwrites packs)."""
import os, json, shutil, zipfile, hashlib, copy
from PIL import Image
CAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.path.dirname(CAT)
T = json.load(open(f'{CAT}/_template/product.json'))
LJ = {d['id']: d for d in json.load(open(f'{ROOT}/etsy_samples/listings/listings.json'))}
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
JLC_SHIP = {"amount": 6.05, "basis": "estimate", "ref": "JLC quote 2026-10-09 for brick figures (US Global Standard); not quoted for this product", "date": "2026-10-09", "region": "US"}
WJP_LT = {"build": 5, "ship_min": 8, "ship_max": 13}

def new(sku, name, fam, kind, proc, parents):
    pk = f'{CAT}/packs/{sku}'
    if os.path.exists(pk): shutil.rmtree(pk)
    for d in ('print', 'listing', 'preview', 'evidence', 'samples'): os.makedirs(f'{pk}/{d}')
    P = copy.deepcopy(T); P.update(sku=sku, name=name, family=fam, kind=kind, parents=parents)
    P['manufacture']['process'] = proc
    P['manufacture']['print_file']['format'] = json.load(open(f'{CAT}/config.json'))['processes'][proc]['print_format']
    return pk, P

def zip_files(dst, files):
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in files: z.write(f, os.path.basename(f))

def set_print(pk, P, path):
    P['manufacture']['print_file'].update(path=os.path.relpath(path, pk), sha256=sha(path))

def etsy_listing(pk, P, pid, alts):
    d = LJ[pid]; L = P['listing']
    L.update(title=d['title'], tags=d['tags'], materials=d['materials'], description=d['desc'], spec_rows=d['spec'],
             processing=d['processing'], price={"currency": "GBP", "amount": float(d['price'].strip('£'))})
    src = f'{ROOT}/etsy_samples/listings/{pid}'
    for i, f in enumerate(sorted(x for x in os.listdir(src) if x.endswith('.jpg'))):
        out = f[:-4] + '.png'; Image.open(f'{src}/{f}').convert('RGB').save(f'{pk}/listing/{out}')
        role = 'hero' if f.startswith('01') else ('spec' if 'spec' in f else 'view')
        L['images'].append(dict(file=out, role=role, alt=alts.format(view=f[3:-4].replace('_', ' '))))
    shutil.copy(f'{src}/listing.txt', f'{pk}/listing/listing.txt')
    P['assets']['listing_source'] = os.path.relpath(src, ROOT)
    P['ext']['listing_images_note'] = 'rendered in Blender from the design-part OBJs (etsy_samples/r0N_*.py), NOT from the print file; re-render from print/ and register to pass G11'

def save(pk, P):
    json.dump(P, open(f'{pk}/product.json', 'w'), indent=1, ensure_ascii=False)

def text_slot(id_, label, cap, mn, maxc, zone, validated=False, evidence=None, fit='shrink-then-fallback-then-error'):
    return dict(id=id_, type='text', label=label, required=id_ == 'name', offered=True, validated=validated, evidence=evidence,
                surface=dict(kind='planar', anchor=zone), method='relief' if not validated else 'relief',
                text=dict(font='Fraunces-SemiBold', cap_mm=cap, min_cap_mm=mn, max_chars=maxc, charset="A-Z 0-9 '&-.!", fit=fit),
                profile_source=['subject.display_name'] if id_ == 'name' else [])

AUD_DAD = lambda suits, occ, ints: dict(suits=suits, occasions=occ, interests=ints, relationship_to_buyer=['dad', 'grandad', 'partner', 'friend'],
                                       not_for=['children under 3 (small parts)'], price_band=None, tone=['funny-affectionate'])

# ---------- 1. Big pet figure ----------
pk, P = new('FIG-PETBIG-TUX-80', 'Me & My Big Pet custom figurine, 80 mm (tuxedo cat sample)', 'figure-with-pet', 'personalised', 'wjp', ['TPL-FIG-PETBIG'])
old = json.load(open(f'{ROOT}/pipeline/products/FIG-PETBIG-TUX-80.json'))
shutil.copy(f'{ROOT}/pipeline/work/bigpet/h80/bigpet-80-jlc.zip', f'{pk}/print/FIG-PETBIG-TUX-80-wjp.zip')
shutil.copy(f'{ROOT}/pipeline/work/bigpet/h80/prep_report.json', f'{pk}/print/prep_report.json')
set_print(pk, P, f'{pk}/print/FIG-PETBIG-TUX-80-wjp.zip')
P['geometry'].update(dims_mm=old['geometry']['dims_mm'], volume_cm3=old['geometry']['volume_cm3'], faces=old['geometry']['faces'], shells=1,
                     size_variants_mm=[60, 80, 100], locked_features=old['geometry']['locked_features'], source=old['geometry']['source'])
M = P['manufacture']; M.update(material='Full Color Resin', finish='Oil Spraying (clear gloss)', colour='Multicolor (texture)', lead_time_days=WJP_LT,
    supplier_settings=old['manufacture']['jlc_settings'])
M['preflight']['acknowledged'] = {"zip size": "8.5 MB; upload it, fall back to a 4k texture if JLC's uploader rejects it",
    "thin walls < 0.8 mm": "whiskers/ear edges; tick the thin-wall risk box (JLC flags every figure)",
    "self-intersections": "person touches cat; WJP fuses overlapping shells"}
P['cost']['print'] = dict(amount=58.58, basis='estimate', ref='preflight volume x $0.82/cm3 (2026-10-09 size sweep)', date='2026-10-10')
P['cost']['shipping'] = JLC_SHIP
slots = old['slots']
for s in slots:
    s['offered'] = s['id'] == 'subject'; s['validated'] = s['id'] == 'subject'
    s['evidence'] = 'print/preflight.json' if s['id'] == 'subject' else None
    s.pop('ext', None)
slots[0]['ext'] = {}  # subject mesh slot: proven by this pack's own sample mesh passing preflight
P['slots'] = slots
P['audience'] = old['audience']; P['audience'].setdefault('relationship_to_buyer', [])
L = P['listing']; ol = old['listing']
L.update(title=ol['title'], tags=ol['tags'], short=ol['short'], description=ol['description'] + "\n\nHow it works: order, then send one full-body photo of you and 1-3 clear photos of your pet. We sculpt both, send you a preview, and print once you approve. Each piece is printed in full-colour resin, so the colour runs through the model, then clear-coated.",
         spec_rows=ol['spec_rows'], materials=['full colour resin', 'clear gloss coat'], processing='Made to order: preview in 2-3 days, then about 5 days production plus shipping')
for f, role, alt in [('bigpet_hero.png', 'hero', 'Full-colour figurine of a woman holding a giant tuxedo cat, three-quarter view'),
                     ('bigpet_front.png', 'view', 'Front view of the pet and owner figurine'),
                     ('bigpet_side.png', 'view', 'Side view showing the oversized cat'),
                     ('bigpet_back.png', 'view', 'Back view of the figurine on its round base')]:
    shutil.copy(f'{ROOT}/pipeline/work/bigpet/h80/listing/{f}', f'{pk}/listing/{f}'); L['images'].append(dict(file=f, role=role, alt=alt))
P['assets'] = dict(master=old['assets']['master'], work_dir='pipeline/work/bigpet/h80', excluded_images={'bigpet_detail.png': 'misframed (chin crop); re-render before use'})
P['graph'] = dict(related=[{"sku": "CHARM-CROC-PET", "rel": "same-subject-smaller"}], extends_to=['size 60/100 mm variants', 'dog version', 'memorial copy'])
save(pk, P)

# ---------- 2-4. Croc charms ----------
def charm(sku, name, srcdir, zsrc, proc, mat, dims, vol, pid=None):
    pk, P = new(sku, name, 'croc-charm', 'personalised', proc, ['TPL-CROC-G07'])
    z = f'{pk}/print/{sku}-{proc}.zip'
    if zsrc: shutil.copy(zsrc, z)
    else: zip_files(z, [f'{srcdir}/{f}' for f in sorted(os.listdir(srcdir))])
    set_print(pk, P, z)
    P['geometry'].update(dims_mm=dims, volume_cm3=vol, shells=1, locked_features=[
        dict(id='stem', note='4.2 mm stem + 6.8 mm stopper (Crocs hole fit); never change'), dict(id='face_max', note='face <= 26 mm for this line')])
    P['manufacture'].update(material=mat, finish='Oil Spraying (clear gloss)', colour='Multicolor (texture)', lead_time_days=WJP_LT)
    P['cost']['print'] = dict(amount=6.91, basis='estimate', ref='JLC WJP floor price seen 2026-10-09', date='2026-10-09'); P['cost']['shipping'] = JLC_SHIP
    P['slots'] = [dict(id='subject', type='mesh' if 'PET' in sku or 'CLIMBER' in sku else 'image', label='Your face / pet', required=True, offered=True, validated=False,
                       evidence=None, surface=dict(kind='whole-model'), method='subject-mesh', preview='mesh-render')]
    P['graph'] = dict(related=[], extends_to=['golf, footy and pet charm sets'])
    if pid:
        etsy_listing(pk, P, pid, 'Croc charm with cartoon Chris badge, {view}')
        P['audience'] = AUD_DAD(['Crocs wearers who like a laugh', 'golfers', 'people who collect Jibbitz'], ['birthday', 'Christmas stocking'], ['crocs', 'golf'])
    return pk, P
pk, P = charm('CHARM-CROC-CHRIS', 'Personalised croc charm, cartoon face badge (Chris sample)', f'{ROOT}/etsy_samples/out/p07_croc_charm/jlc', None, 'wjp',
              'Full Color Resin', [26.0, 26.0, 11.1], 1.92, 'p07_croc_charm'); save(pk, P)
pk, P = charm('CHARM-CROC-CLIMBER', 'Croc charm: hole climber', None, f'{ROOT}/charms/out/croc-charm-climber-jlc.zip', 'wjp-tough', 'Full Color Tough Resin', None, None)
P['ext']['note'] = 'dims/volume fill in from preflight'; save(pk, P)
pk, P = charm('CHARM-CROC-PET', 'Croc charm: pet head', None, f'{ROOT}/charms/out/croc-charm-pet-jlc.zip', 'wjp-tough', 'Full Color Tough Resin', [15.62, 16.0, 22.3], 1.60)
save(pk, P)

# ---------- 5-13. Etsy samples ----------
import trimesh
os.makedirs(f'{ROOT}/etsy_samples/out/_dart_print', exist_ok=True)
trimesh.load(f'{ROOT}/etsy_samples/out/p04_dart_stand.stl').export(f'{ROOT}/etsy_samples/out/_dart_print/STAND-DART-MJF.obj')  # body+paint union = the real print body
E = f'{ROOT}/etsy_samples/out'
def sample(sku, name, fam, proc, tpl, pid, mat, fin, col, meta_key, print_parts, hand, slots, aud, locked, alt):
    pk, P = new(sku, name, fam, 'personalised', proc, [tpl])
    meta = json.load(open(f'{E}/{pid}/meta.json')); pr = meta.get('_print') or meta.get(meta_key) or {}
    P['geometry'].update(dims_mm=pr.get('ext_mm') or pr.get('ext'), volume_cm3=pr.get('vol_cm3') or pr.get('vol'), shells=pr.get('bodies'), locked_features=locked)
    if print_parts:
        z = f'{pk}/print/{sku}-{proc}.zip'; zip_files(z, [f'{E}/{pid}/{p}' for p in print_parts]); set_print(pk, P, z)
    P['manufacture'].update(material=mat, finish=fin, colour=col, hand_finish=hand, lead_time_days=WJP_LT if proc.startswith('wjp') else {"build": None, "ship_min": None, "ship_max": None})
    est = {'wjp': 0.82, 'mjf': 0.35, 'slm-316l': None, 'cnc': None}[proc]
    v = P['geometry']['volume_cm3']
    P['cost']['print'] = dict(amount=round(max(6.91 if proc == 'wjp' else 3.0, v * est), 2) if est and v else None, basis='estimate' if est else None,
                              ref='volume x preflight rate' if est else None, date='2026-10-10' if est else None)
    P['cost']['shipping'] = JLC_SHIP
    P['slots'] = slots; P['audience'] = aud
    P['assets'] = dict(design_parts=f'etsy_samples/out/{pid}/', generator=f'etsy_samples/g0{pid[2]}_*.py' if pid[1] == '0' else '')
    etsy_listing(pk, P, pid, alt)
    return pk, P

GOLF = ['golfers', 'dads who play off a terrible handicap', 'people who have everything']
pk, P = sample('MARKER-GOLF-CNC', 'Personalised golf ball marker, black anodised aluminium', 'golf-marker', 'cnc', 'TPL-GOLF-MARKER', 'p01_golf_marker',
    '6061 aluminium', 'black anodise + laser mark both faces', 'black', 'marker', None, [],
    [text_slot('name', 'Name (front)', 3.0, 1.5, 10, 'front ring'), text_slot('message', 'Message (back)', 2.0, 1.2, 24, 'back face')],
    AUD_DAD(GOLF, ['birthday', "Father's Day", 'Christmas', 'retirement'], ['golf']), [dict(id='disc', note='24 mm dia x 2.0 mm (marker standard)')],
    'Engraved black aluminium golf ball marker, {view}')
P['ext']['blocker'] = 'JLC CNC quotes need a STEP file; we only have mesh OBJ. Laser marking is a separate JLC finishing option to confirm.'; save(pk, P)

pk, P = sample('MAHJ-READER-WJP', 'Personalised mahjong line reader, jade + ivory', 'mahjong-reader', 'wjp', 'TPL-MAHJ-READER', 'p02_line_reader',
    'Full Color Resin', 'Oil Spraying (clear gloss)', 'jade + ivory', 'reader', None, [],
    [text_slot('name', 'Name', 6.0, 3.0, 10, 'top bar'), text_slot('tagline', 'Tagline', 3.0, 2.0, 24, 'bottom bar')],
    dict(suits=['mahjong players', 'NMJL card holders', 'game-night hosts'], occasions=['birthday', 'Christmas', 'Mother\'s Day'], interests=['mahjong', 'games'],
         relationship_to_buyer=['mum', 'gran', 'friend', 'dad'], not_for=['non-NMJL card sizes (check card width)'], price_band='£15-20', tone=['playful']),
    [dict(id='window', note='reading window = one NMJL card line')], 'Personalised jade mahjong line reader, {view}')
P['ext']['blocker'] = 'multi-part design (body + relief); WJP needs ONE textured OBJ+MTL+PNG: bake the part colours into a texture'; save(pk, P)

pk, P = sample('RACK-CARD-MJF', 'Personalised playing-card hand rack, black PA12', 'card-rack', 'mjf', 'TPL-CARD-RACK', 'p03_card_rack',
    'PA12 nylon (MJF)', 'dyed black', 'black', 'rack', ['rack.obj'], ['gold paint-fill of engraved name and suits (fill.obj)'],
    [text_slot('name', 'Name (engraved)', 6.0, 3.0, 10, 'front face')],
    AUD_DAD(['card players with arthritis or small hands', 'cribbage and rummy regulars', 'grandparents who host card night'], ['birthday', 'Christmas'], ['cards', 'games']),
    [dict(id='grooves', note='3 grooves 2.5 mm, length 200 mm')], 'Black card hand rack engraved with a name, {view}')
save(pk, P)

dspec = 'dart/personalisation_spec.json'
pk, P = sample('STAND-DART-MJF', 'Personalised dart stand, dartboard relief, black PA12', 'dart-stand', 'mjf', 'TPL-DART-STAND', 'p04_dart_stand',
    'PA12 nylon (MJF)', 'dyed black', 'black', 'body', ['../_dart_print/STAND-DART-MJF.obj'], ['gold paint of relief name/arc/bands (paint.obj)'],
    [text_slot('name', 'Name (banner)', 7.4, 5.0, 10, 'front banner', True, dspec),
     text_slot('tagline', 'Tagline (banner)', 2.4, 2.4, 16, 'banner under name', True, dspec),
     text_slot('arc', 'Rim arc', 3.4, 3.4, 18, 'rim front arc', True, dspec),
     dict(id='base_colour', type='colour', label='Base colour', required=False, offered=False, validated=True, evidence=dspec, surface=dict(kind='material'), method='dyed/printed',
          colour=dict(palette=['midnight', 'white', 'navy', 'racing-green', 'oddhobb-orange', 'red'], default='midnight'))],
    AUD_DAD(['darts players', 'pub league regulars', 'man-cave owners'], ['birthday', "Father's Day", 'Christmas'], ['darts', 'pub games']),
    [dict(id='bores', note='3 bores 12.4 mm x 40 deep (12 mm barrel + clearance)')], 'Black personalised dart stand with dartboard relief, {view}')
P['slots'][0]['profile_source'] = ['subject.display_name']; P['slots'][2]['profile_source'] = ["relation + \"'S DARTS\""]
P['ext']['note'] = 'slot schema live-tested 2026-10-10 (43/43 tests); plates for true-perspective preview still TODO'
save(pk, P)

pk, P = sample('PEGS-CRIB-316L', 'Cribbage pegs: golf-ball + flag set, engraved', 'cribbage-pegs', 'slm-316l', 'TPL-CRIB-PEG', 'p05_cribbage_pegs',
    '316L stainless steel', 'polished', 'steel', 'ball_peg', ['ball_peg.obj', 'flag_peg.obj'], [],
    [text_slot('initials', 'Initials (flag)', 2.0, 2.0, 3, 'flag face')],
    AUD_DAD(['cribbage players', 'golfers who play crib', 'collectors of game pieces'], ['birthday', 'Christmas'], ['cribbage', 'golf']),
    [dict(id='shaft', note='3.1 mm x 14 mm shaft (1/8" holes)')], 'Steel cribbage pegs shaped like golf balls and flags, {view}')
P['ext']['blocker'] = 'two parts in one zip; JLC needs one model per line item (split into two print files or one merged body)'; save(pk, P)

for sku, name, fam, tpl, pid, key, mesh, aud, locked, alt in [
    ('KEYCAP-MX-WJP', 'Artisan keycap: 19th hole (Cherry MX)', 'keycap', 'TPL-KEYCAP-MX', 'p06_keycap', 'cap', False,
     dict(suits=['mechanical keyboard fans', 'golfers who work at a desk', 'gamers'], occasions=['birthday', 'Christmas stocking'], interests=['keyboards', 'golf'],
          relationship_to_buyer=['partner', 'friend', 'dad'], not_for=['low-profile or non-MX switches'], price_band=None, tone=['playful']),
     [dict(id='stem', note='Cherry MX cross 4.15 x 1.32, 4.6 deep')], 'Golf green artisan keycap, {view}'),
    ('KEYCHAIN-BUST-WJP', 'Mini-me bust keychain from photos', 'keychain', 'TPL-KEYCHAIN', 'p08_keychain', 'chris', True,
     AUD_DAD(['people who love a mini-me', 'dads', 'new drivers'], ['birthday', "Father's Day", 'Christmas stocking'], ['mini-me']), [dict(id='loop', note='printed loop, 4.0 mm ring hole')],
     'Full-colour mini bust keychain, {view}'),
    ('ORNAMENT-SANTA-WJP', 'Mini-me Christmas ornament with Santa hat', 'ornament', 'TPL-ORNAMENT', 'p09_ornament', 'chris', True,
     AUD_DAD(['families', 'first Christmas together', 'grandparents'], ['Christmas', 'first Christmas'], ['christmas', 'mini-me']), [dict(id='loop', note='5.0 mm loop hole / 2.4 mm wire')],
     'Full-colour mini-me Christmas ornament, {view}'),
    ('FIG-MINI-GOLF-WJP', 'Mini-me desk figure on putting green', 'mini-figure', 'TPL-MINI-FIG', 'p10_mini_figure', 'chris', True,
     AUD_DAD(GOLF, ['birthday', 'retirement', "Father's Day", 'Christmas'], ['golf', 'mini-me']), [dict(id='scale', note='75 mm class figure, 66 mm subject')],
     'Full-colour mini-me golfer desk figure, {view}')]:
    slots = [text_slot('name', 'Name', 3.0, 1.5, 10, 'name plate')]
    if mesh: slots.insert(0, dict(id='subject', type='mesh', label='Their mini-me (from photos)', required=True, offered=True, validated=False, evidence=None, surface=dict(kind='whole-model'), method='subject-mesh'))
    pk, P = sample(sku, name, fam, 'wjp', tpl, pid, 'Full Color Resin', 'Oil Spraying (clear gloss)', 'Multicolor (texture)', key, None, [], slots, aud, locked, alt)
    P['ext']['blocker'] = 'multi-part colour design; WJP needs ONE textured OBJ+MTL+PNG (bake part colours into the subject atlas)'
    save(pk, P)
print('imported', len(os.listdir(f'{CAT}/packs')), 'packs')
