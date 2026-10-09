import json, os, sys, glob
from PIL import Image, ImageDraw, ImageFont, ImageChops
E='/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples'
F=lambda w,s: ImageFont.truetype(f'{E}/listings/inter/extras/ttf/Inter-{w}.ttf',s)
BG=(244,244,244); INK=(22,22,24); GREY=(128,128,130); S=2000
NAMES={'p01_golf_marker':'Golf Ball Marker','p02_line_reader':'Mahjong Line Reader','p03_card_rack':'Card Hand Rack','p04_dart_stand':'Dart Stand','p05_cribbage_pegs':'Cribbage Peg Pair','p06_keycap':'Artisan Keycap','p07_croc_charm':'Croc Charm','p08_keychain':'3D Face Keychain','p09_ornament':'Christmas Ornament','p10_mini_figure':'Mini Me Figure'}
SEL={'p07_croc_charm':['high34','top','34','high34'],'p01_golf_marker':['high34','top','under','high34'],'p02_line_reader':['high34','top','detail:top:0.02,0.35,0.62,1.0','high34']}
PREF=['34','high34','front','top','side','back','back34','under']
def obj(path):
    im=Image.open(path).convert('RGB'); bg=Image.new('RGB',im.size,BG)
    d=ImageChops.difference(im,bg).convert('L').point(lambda v:255 if v>6 else 0); bb=d.getbbox()
    return im.crop(bb) if bb else im
def load(v):
    if isinstance(v,tuple):
        o=obj(v[1]); b=v[2]; return o.crop((int(b[0]*o.width),int(b[1]*o.height),int(b[2]*o.width),int(b[3]*o.height)))
    return obj(v)
def fit(im,box):
    w,h=box; r=min(w/im.width,h/im.height); return im.resize((max(1,int(im.width*r)),max(1,int(im.height*r))),Image.LANCZOS)
def placed(im,area,top=0):
    c=Image.new('RGB',(S,S),BG); f=fit(im,area); c.paste(f,((S-f.width)//2,top+(area[1]-f.height)//2)); return c
def hero(pid):
    for p in [f'{E}/out/{pid}.png',f'{E}/out/{pid}_fast_raw.png']:
        if os.path.exists(p):
            im=Image.open(p).convert('RGB'); s=min(im.size); im=im.crop(((im.width-s)//2,(im.height-s)//2,(im.width+s)//2,(im.height+s)//2))
            return im.resize((S,S),Image.LANCZOS), ('final' if not p.endswith('fast_raw.png') else 'preview')
    return None,None
def spec_card(pid,view,L):
    c=placed(load(view),(1500,1080),top=110); d=ImageDraw.Draw(c)
    d.line([(160,1290),(S-160,1290)],fill=(214,214,214),width=3)
    d.text((160,1340),NAMES[pid],font=F('SemiBold',92),fill=INK)
    d.text((S-160,1362),L['price'],font=F('Medium',64),fill=GREY,anchor='ra')
    for i,(k,v) in enumerate(L['spec']):
        y=1500+i*95
        d.text((160,y),k.upper(),font=F('SemiBold',34),fill=GREY)
        fs=48
        while F('Medium',fs).getlength(v)>1180: fs-=2
        d.text((S-160,y-6),v,font=F('Medium',fs),fill=INK,anchor='ra')
    d.text((S//2,1915),'PERSONALISED  ·  MADE TO ORDER',font=F('SemiBold',30),fill=GREY,anchor='mm')
    return c
L={l['id']:l for l in json.load(open(f'{E}/listings/listings.json'))}
for pid in (sys.argv[1:] or L):
    import shutil; shutil.rmtree(f'{E}/listings/{pid}',ignore_errors=True)
    vs={v:f'{E}/out/views/{pid}_{v}.png' for v in PREF if os.path.exists(f'{E}/out/views/{pid}_{v}.png')}
    want=SEL.get(pid,['34','front','side','back'])
    for w in want:
        if w.startswith('detail:'):
            _,src,box=w.split(':'); b=[float(x) for x in box.split(',')]
            if src in vs: vs[w]=('crop',vs[src],b)
    order=[v for v in want if v in vs]
    if len(order)<4: order=order+[v for v in PREF if v in vs and v not in order]
    if len(order)<4: print('SKIP',pid,'views',order); continue
    od=f'{E}/listings/{pid}'; os.makedirs(od,exist_ok=True)
    h,kind=hero(pid); h.save(f'{od}/01_hero.jpg',quality=92)
    for i,v in enumerate(order[:3]): placed(load(vs[v]),(1700,1700),top=150).save(f'{od}/0{i+2}_{v.split(":")[0]}.jpg',quality=92)
    spec_card(pid,order[3] and vs[order[3]],L[pid]).save(f'{od}/05_spec.jpg',quality=92)
    open(f'{od}/listing.txt','w').write(f"TITLE\n{L[pid]['title']}\n\nPRICE\n{L[pid]['price']}\n\nDESCRIPTION\n{L[pid]['desc']}\n\nTAGS\n{', '.join(L[pid]['tags'])}\n\nMATERIALS\n{', '.join(L[pid]['materials'])}\n\nPROCESSING\n{L[pid]['processing']}\n")
    print('LISTING',pid,'hero='+kind,'views='+','.join(order[:4]))
