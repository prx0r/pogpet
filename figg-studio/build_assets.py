from pathlib import Path
import re, io, json, zipfile, math
from PIL import Image, ImageOps, ImageDraw
import cairosvg

ROOT=Path(__file__).resolve().parent
SVGD=ROOT/'assets/mascots/svg'; PNGD=ROOT/'assets/mascots/png'; LOGO=ROOT/'assets/logos'; PAT=ROOT/'assets/patterns'; TEMP=ROOT/'assets/templates'; PRE=ROOT/'assets/previews'
P='#8B3DFF'; DARK='#111111'; LIGHT='#EAD8FF'; W='#FAFAF8'
VARIANTS=[
 ('01','classic','The original','core'), ('02','wink','A little wink','core'),('03','sitting','Take five','core'),('04','tall','Standing tall','core'),
 ('05','joy','Pure joy','core'),('06','side','From the side','core'),('07','wave','Hi there','core'),('08','sleepy','Slow mornings','core'),
 ('09','sparkle','Magic moment','expressions'),('10','crown','Little royalty','occasions'),('11','curious','Curious figg','expressions'),('12','scarf','Wrapped up','occasions'),
 ('13','heart','With love','occasions'),('14','headphones','In my zone','accessories'),('15','cheeky','A cheeky hello','expressions'),('16','shades','Incognito','accessories'),
 ('17','tilt','A new angle','core'),('18','nap','Extra cozy','expressions'),('19','jump','Can’t contain it','expressions'),('20','quiet','Just here','core'),
 ('21','bashful','Blushing','expressions'),('22','sprout','Growing on you','accessories'),('23','cap','Out and about','accessories'),('24','star','You’re a star','occasions'),
 ('25','back','See you soon','core'),('26','bow','Dressed up','accessories'),('27','cheer','Big day','expressions'),('28','hoodie','Comfy club','accessories'),
 ('29','glasses','A bright idea','accessories'),('30','belly','Grounded','expressions'),('31','love','Little crush','occasions'),('32','cosmic','Night mode','occasions')]
# A purpose-drawn reusable vector mascot. No font files or external image references.
def mascot(n=1, size=512, include_bg=False, custom=None):
    idx=max(1,min(32,int(n))); _, key, _,_=VARIANTS[idx-1]
    sleepy=key in ('sleepy','nap','joy','cheer'); wink=key in ('wink','cheeky','bashful');
    side=key=='side'; back=key=='back'; seated=key in ('sitting','nap','belly','curious')
    raised=key in ('wave','cheer','jump'); cosmic=key=='cosmic'
    squash=key in ('nap','belly','curious')
    # silhouette remains consistent even when the accessories differ
    body='M256 65 C242 81 244 104 213 122 C141 166 82 208 82 293 C82 380 157 431 256 431 C355 431 430 380 430 293 C430 215 369 169 307 125 C272 100 276 81 280 56 C267 53 261 57 256 65Z'
    if key=='tall': body='M256 42 C240 62 244 94 215 120 C162 168 104 205 104 293 C104 388 166 444 256 444 C346 444 408 388 408 293 C408 209 349 166 303 124 C266 94 280 64 281 36 C268 32 261 34 256 42Z'
    if squash: body='M256 150 C239 159 237 178 210 184 C147 204 79 238 79 326 C79 394 158 432 256 432 C354 432 433 394 433 326 C433 245 355 201 304 183 C278 175 281 160 279 148 C271 145 261 145 256 150Z'
    if cosmic: body_gradient='url(#cosmic)'
    else: body_gradient='url(#body)'
    fx=[]
    if include_bg:
        fx.append('<rect width="512" height="512" rx="104" fill="#F2EAFF"/>')
    fx.append('''<defs>
     <linearGradient id="body" x1="0" y1="0" x2=".94" y2="1" gradientUnits="objectBoundingBox"><stop offset="0" stop-color="#CB94FF"/><stop offset=".26" stop-color="#AC64F6"/><stop offset=".56" stop-color="#9343EA"/><stop offset=".85" stop-color="#792FD5"/><stop offset="1" stop-color="#6425B9"/></linearGradient>
     <radialGradient id="light" cx=".23" cy=".11" r=".85"><stop offset="0" stop-color="#F4DEFF" stop-opacity=".78"/><stop offset=".45" stop-color="#D9A3FF" stop-opacity=".13"/><stop offset="1" stop-color="#7140D7" stop-opacity="0"/></radialGradient>
     <linearGradient id="foot" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#A75EF0"/><stop offset="1" stop-color="#6329AD"/></linearGradient>
     <linearGradient id="cosmic" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#D6A7FF"/><stop offset=".32" stop-color="#B25FFF"/><stop offset=".75" stop-color="#713EC4"/><stop offset="1" stop-color="#4E267F"/></linearGradient>
     <radialGradient id="eye" cx=".28" cy=".20" r=".87"><stop offset="0" stop-color="#2E1942"/><stop offset="1" stop-color="#120F1B"/></radialGradient>
     <filter id="shadow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="9"/></filter>
     </defs>''')
    if key=='jump': fx.append('<ellipse cx="258" cy="468" rx="108" ry="14" fill="#332B42" opacity=".14" filter="url(#shadow)"/>')
    else: fx.append('<ellipse cx="258" cy="451" rx="119" ry="15" fill="#332B42" opacity=".16" filter="url(#shadow)"/>')
    if not seated and not back and key!='jump':
        fx.append('<path d="M187 404 C179 421 177 442 190 447 C203 453 219 449 225 433 L229 412Z" fill="url(#foot)"/><path d="M283 412 L287 433 C293 449 310 453 323 447 C337 440 332 418 324 404Z" fill="url(#foot)"/>')
    if seated:
        fx.append('<ellipse cx="164" cy="412" rx="35" ry="23" fill="url(#foot)"/><ellipse cx="348" cy="412" rx="35" ry="23" fill="url(#foot)"/>')
    if key=='jump':fx.append('<ellipse cx="198" cy="432" rx="25" ry="14" transform="rotate(-30 198 432)" fill="url(#foot)"/><ellipse cx="322" cy="432" rx="25" ry="14" transform="rotate(30 322 432)" fill="url(#foot)"/>')
    if key=='wave': fx.append('<path d="M104 294 C71 270 59 249 71 234 C84 217 106 248 132 251Z" fill="#A968F0"/>')
    if key in ('cheer','jump'):fx.append('<path d="M100 280 Q48 248 74 218 Q90 209 128 244Z M400 275 Q456 247 432 217 Q412 210 385 245Z" fill="#A862EF"/>')
    if key=='heart':fx.append('<path d="M120 331 Q75 322 91 298 Q112 276 143 308Z M392 331 Q434 323 420 299 Q403 281 370 306Z" fill="#9945DD"/>')
    if key=='star':fx.append('<path d="M119 314 Q82 301 87 278 Q107 262 145 296Z M398 314 Q430 293 420 277 Q397 266 367 294Z" fill="#9945DD"/>')
    if key=='side':fx.append('<path d="M350 323 Q406 311 414 351 Q417 383 373 376Z" fill="#9550DC"/>')
    fx.append(f'<path d="{body}" fill="{body_gradient}" stroke="#6630AB" stroke-width=".9"/>')
    fx.append(f'<path d="{body}" fill="url(#light)" opacity=".58"/>')
    # curvilinear shoulder reflection and lower bounce light
    fx.append('<path d="M146 211 Q119 249 116 290" fill="none" stroke="#EBD0FF" stroke-opacity=".32" stroke-width="10" stroke-linecap="round"/>')
    if cosmic:
        for x,y,r in [(150,229,2.6),(285,138,2.2),(336,256,1.6),(305,353,1.8),(222,402,1.5),(191,321,2.2),(356,328,1.5)]:
            fx.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#F5E8FF" opacity=".7"/>')
    if not back:
        if side:
            fx.extend(['<ellipse cx="314" cy="284" rx="18" ry="26" fill="url(#eye)"/>','<ellipse cx="308" cy="275" rx="5" ry="8" fill="white"/>','<path d="M348 324 Q354 330 348 333" fill="none" stroke="#261A2F" stroke-width="5" stroke-linecap="round"/>'])
        elif sleepy:
            fx.extend(['<path d="M169 294 Q192 266 213 292" stroke="#201526" stroke-width="9" fill="none" stroke-linecap="round"/>','<path d="M297 292 Q320 266 342 294" stroke="#201526" stroke-width="9" fill="none" stroke-linecap="round"/>'])
        elif wink:
            fx.extend(['<ellipse cx="190" cy="287" rx="19" ry="27" fill="url(#eye)"/>','<ellipse cx="185" cy="278" rx="5.5" ry="8" fill="white"/>','<path d="M300 291 Q326 272 347 291" fill="none" stroke="#201526" stroke-width="10" stroke-linecap="round"/>'])
        else:
            fx.extend(['<ellipse cx="190" cy="287" rx="19" ry="27" fill="url(#eye)"/>','<ellipse cx="322" cy="287" rx="19" ry="27" fill="url(#eye)"/>','<ellipse cx="185" cy="277" rx="5.5" ry="8.5" fill="white"/>','<ellipse cx="317" cy="277" rx="5.5" ry="8.5" fill="white"/>'])
        if key in ('joy','cheer','jump','bashful','love'):fx.append('<ellipse cx="149" cy="319" rx="20" ry="10" fill="#F9A6D9" opacity=".73"/><ellipse cx="363" cy="319" rx="20" ry="10" fill="#F9A6D9" opacity=".73"/>')
        if key in ('sleepy','nap'):fx.append('<path d="M246 338 Q256 345 266 338" stroke="#281B32" stroke-width="5" stroke-linecap="round" fill="none"/>')
        elif key in ('joy','cheer','jump'):fx.append('<path d="M243 336 Q256 359 269 336" stroke="#281B32" stroke-width="6" stroke-linecap="round" fill="none"/>')
        else:fx.append('<path d="M246 334 Q256 343 266 334" stroke="#251729" stroke-width="5" stroke-linecap="round" fill="none"/>')
    # Accessories, intentionally minimal and symbolic
    if key=='sparkle':fx.append('<path d="M393 174 L405 209 L440 221 L405 233 L393 268 L381 233 L346 221 L381 209Z" fill="#8B3DFF"/>')
    if key=='crown':fx.append('<path d="M210 137 L210 111 L232 126 L255 93 L282 127 L302 111 L300 139Z" fill="#7631CF" stroke="#A96BF8" stroke-width="5"/><circle cx="255" cy="119" r="5" fill="#E8CCFF"/>')
    if key=='scarf':fx.append('<path d="M133 347 Q253 372 377 346 L374 375 Q253 401 143 374Z" fill="#5F269F"/><path d="M317 365 L350 365 L354 427 Q337 442 323 427Z" fill="#7032BC"/>')
    if key=='heart':fx.append('<path d="M256 401 C234 377 192 362 194 332 C196 304 236 300 256 323 C279 297 316 306 318 332 C320 360 280 381 256 401Z" fill="#FFF9FF" stroke="#EDE0FF" stroke-width="3"/>')
    if key=='headphones':fx.append('<path d="M125 279 C111 145 170 122 252 122 C345 122 397 167 389 280" fill="none" stroke="#54258F" stroke-width="24"/><rect x="104" y="263" width="49" height="95" rx="23" fill="#F9F7FF" stroke="#AA8DDF" stroke-width="5"/><rect x="362" y="263" width="49" height="95" rx="23" fill="#F9F7FF" stroke="#AA8DDF" stroke-width="5"/>')
    if key in ('shades','glasses'):fx.append('<path d="M148 279 L365 279" stroke="#EAE4F9" stroke-width="11"/><circle cx="192" cy="287" r="37" fill="#F4E8FF" stroke="#FBF6FF" stroke-width="12" fill-opacity=".3"/><circle cx="319" cy="287" r="37" fill="#F4E8FF" stroke="#FBF6FF" stroke-width="12" fill-opacity=".3"/>')
    if key=='sprout':fx.append('<path d="M258 93 Q265 42 309 38 Q298 90 258 93Z" fill="#7330BF" stroke="#9C5CEB" stroke-width="3"/><path d="M258 94 Q261 71 286 52" fill="none" stroke="#C999FF" stroke-width="3"/>')
    if key=='cap':fx.append('<path d="M169 211 Q154 157 208 142 Q273 128 332 158 L348 206 Q275 189 169 211Z" fill="#FBF8FF"/><path d="M163 206 Q272 186 375 201 Q352 224 271 226 Q214 229 163 206Z" fill="#E9DDFF"/><text x="237" y="190" font-size="31" fill="#161018" font-family="Arial,sans-serif" font-weight="900">f.</text>')
    if key=='star':fx.append('<path d="M256 301 L277 343 L325 350 L290 383 L298 431 L256 409 L213 431 L221 383 L187 350 L235 343Z" fill="#FFF" stroke="#E9DFF7" stroke-width="4"/>')
    if key=='bow':fx.append('<path d="M255 396 Q211 362 196 387 Q194 416 254 410 Q307 419 319 394 Q319 369 255 396Z" fill="#FFF" stroke="#E8DFF8" stroke-width="4"/><circle cx="256" cy="402" r="9" fill="#E4D6FA"/>')
    if key=='hoodie':fx.append('<path d="M154 222 Q179 140 256 146 Q334 143 355 222" fill="none" stroke="#FBFAFF" stroke-width="58" stroke-linecap="round"/><path d="M175 337 Q244 381 340 337 L363 420 Q256 457 152 423Z" fill="#F9F8FD" opacity=".92"/><path d="M244 356 L239 385 M266 356 L271 385" stroke="#A4A2B1" stroke-width="5"/>')
    if key=='love':fx.append('<path d="M399 181 C389 162 363 161 362 184 C360 205 399 223 399 223 C399 223 438 203 437 184 C434 160 409 163 399 181Z" fill="#8B3DFF"/>')
    if key=='cosmic':fx.append('<path d="M183 375 Q253 390 333 365" stroke="#E8D9FF" stroke-width="3" opacity=".16" fill="none"/>')
    s='<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 512 512" role="img" aria-label="figg mascot, %s">%s</svg>'%(size,size,key,''.join(fx))
    return s

def write_png(svg,path, output_width=1024):
    cairosvg.svg2png(bytestring=svg.encode(),write_to=str(path),output_width=output_width,output_height=output_width)

for num,key,title,category in VARIANTS:
    s=mascot(int(num))
    (SVGD/f'{num}-{key}.svg').write_text(s,encoding='utf8')
    write_png(s, PNGD/f'{num}-{key}.png',1024)

# Pure vector logos: deliberately editable SVG text + CSS-system font fallback.
wordmark='<svg xmlns="http://www.w3.org/2000/svg" width="345" height="160" viewBox="0 0 345 160"><title>figg. wordmark</title><text x="1" y="120" font-family="Arial,Helvetica,sans-serif" font-weight="900" font-size="150" letter-spacing="-12" fill="#111111">figg</text><circle cx="254" cy="117" r="14" fill="#8B3DFF"/></svg>'
(LOGO/'figg-wordmark.svg').write_text(wordmark)
(LOGO/'figg-wordmark-white.svg').write_text(wordmark.replace('#111111','#FFFFFF'))
mono=wordmark.replace('#8B3DFF','#111111')
(LOGO/'figg-wordmark-mono.svg').write_text(mono)
(LOGO/'figg-mark.svg').write_text(mascot(1,512,True))
(LOGO/'figg-favicon.svg').write_text(mascot(1,512,True))
write_png(mascot(1,512,True),LOGO/'figg-shop-avatar.png',1024)
# simplify to silhouette-only visual asset for stamps
(LOGO/'figg-silhouette.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="M256 65 C242 81 244 104 213 122 C141 166 82 208 82 293 C82 380 157 431 256 431 C355 431 430 380 430 293 C430 215 369 169 307 125 C272 100 276 81 280 56 C267 53 261 57 256 65Z" fill="#8B3DFF"/></svg>')
# 360° repeat pattern from figure silhouettes and simple shapes
pattern='''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="640" viewBox="0 0 640 640"><rect width="640" height="640" fill="#FAFAF8"/>
 <defs><g id="a"><path d="M0 -56 C-5 -43 -5 -30 -25 -15 C-52 3 -61 27 -61 52 C-61 92 -32 116 0 116 C32 116 61 92 61 52 C61 28 52 2 26 -16 C7 -30 7 -44 10 -59Z" fill="#C9A5FB"/><ellipse cx="-21" cy="53" rx="7" ry="10" fill="#251B2D"/><ellipse cx="22" cy="53" rx="7" ry="10" fill="#251B2D"/><path d="M-5 73 Q0 78 5 73" fill="none" stroke="#251B2D" stroke-width="3"/></g></defs>
 <use href="#a" x="110" y="70" transform="rotate(-12 110 70)"/><use href="#a" x="410" y="198" transform="rotate(17 410 198)"/><use href="#a" x="137" y="382" transform="rotate(16 137 382)"/><use href="#a" x="492" y="514" transform="rotate(-13 492 514)"/>
 <g fill="none" stroke="#A570EC" stroke-width="5" stroke-linejoin="round"><path d="M292 63l12 16 19-7-8 21 16 13-22 2-6 20-11-20-22-2 16-13z"/><path d="M295 360C285 338 254 349 264 369 C271 384 295 396 295 396 C295 396 319 380 324 367 C332 342 300 340 295 360Z"/></g>
 </svg>'''
(PAT/'figg-repeat.svg').write_text(pattern)
write_png(pattern,PAT/'figg-repeat.png',1280)
# print templates are editable SVGs: no exaggerated claims about packing / turnaround.
card=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1748" height="1240" viewBox="0 0 1748 1240"><rect width="1748" height="1240" fill="#FAFAF8"/><rect x="66" y="66" width="1616" height="1108" rx="24" fill="none" stroke="#E5D8F4" stroke-width="3"/><text x="130" y="238" fill="#111" font-family="Arial,sans-serif" font-size="144" font-weight="900" letter-spacing="-9">figg</text><circle cx="397" cy="221" r="16" fill="#8B3DFF"/><text x="130" y="560" fill="#111111" font-family="Arial,sans-serif" font-size="83" font-weight="800">A little something</text><text x="130" y="654" fill="#8B3DFF" font-family="Arial,sans-serif" font-size="83" font-weight="800">just for you.</text><text x="133" y="770" fill="#74707D" font-family="Arial,sans-serif" font-size="33">Made from a photo. Made to make you smile.</text><g transform="translate(1060 206) scale(1.1)">{re.search(r'<svg[^>]*>(.*)</svg>',mascot(2),re.S).group(1)}</g><text x="130" y="1090" fill="#9E92AA" font-family="Arial,sans-serif" font-size="24" letter-spacing="6">LITTLE FIGURES. BIG FEELINGS.</text></svg>'''
# NOTE nested gradients use repeated ids once because outer doc has no defs.
(TEMP/'thank-you-card-a6.svg').write_text(card)
# product-sticker mockup: 3 x 3 in like merch proof not actual manufacturer packaging
sticker=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 900" width="900" height="900"><rect width="900" height="900" rx="450" fill="#FFFFFF"/><circle cx="450" cy="450" r="430" fill="#FBF8FF" stroke="#8B3DFF" stroke-width="22"/>
 <g transform="translate(230 145) scale(.88)">{re.search(r'<svg[^>]*>(.*)</svg>',mascot(1),re.S).group(1)}</g><text x="450" y="725" text-anchor="middle" font-family="Arial,sans-serif" font-weight="900" font-size="136" fill="#111111">figg<tspan fill="#8B3DFF">.</tspan></text></svg>'''
(TEMP/'round-packaging-sticker.svg').write_text(sticker)
# Social post template simple vector for ready asset and designer customization
social='''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1080" viewBox="0 0 1080 1080"><rect width="1080" height="1080" fill="#FAFAF8"/><path d="M0 0H1080V34H0Z" fill="#8B3DFF"/><text x="75" y="150" font-family="Arial,sans-serif" font-size="86" font-weight="900" letter-spacing="-5" fill="#111111">figg<tspan fill="#8B3DFF">.</tspan></text><text x="75" y="302" font-family="Arial,sans-serif" font-size="76" font-weight="800" fill="#111111">little figures.</text><text x="75" y="382" font-family="Arial,sans-serif" font-size="76" font-weight="800" fill="#8B3DFF">big feelings.</text><rect x="475" y="409" width="520" height="550" rx="75" fill="#F0E3FF"/><image href="../mascots/png/01-classic.png" x="495" y="443" width="480" height="480"/><text x="76" y="962" font-family="Arial,sans-serif" font-size="27" fill="#6B6672" letter-spacing="2">A LITTLE FIGURE, MADE FOR YOU.</text></svg>'''
(TEMP/'social-square-editable.svg').write_text(social)
# photo crops from previously approved campaign concepts. Label in site as concept imagery, not actual print proof.
PHOTO=ROOT/'assets/photos'; PHOTO.mkdir(parents=True,exist_ok=True)
source=Path('/mnt/data/one_photo_endless_couple_vibes.png')
if source.exists():
    im=Image.open(source).convert('RGB'); sz=im.size
    # first panel real portrait no headings
    im.crop((22,450,310,1088)).resize((576,1276),Image.Resampling.LANCZOS).save(PHOTO/'couple-portrait-concept.jpg',quality=88,optimize=True)
    im.crop((328,565,622,950)).resize((730,960),Image.Resampling.LANCZOS).save(PHOTO/'couple-figures-concept.jpg',quality=89,optimize=True)
child=Path('/mnt/data/little_imaginations_holiday_gift_ready.png')
if child.exists():
    im=Image.open(child).convert('RGB')
    im.crop((55,215,400,710)).resize((690,990),Image.Resampling.LANCZOS).save(PHOTO/'kids-portrait-concept.jpg',quality=88,optimize=True)
# curated caption gallery data
meta={'name':'figg. mascot library','color':'#8B3DFF','version':'1.0.0','variants':[{'id':n,'slug':k,'name':t,'category':cat,'svg':f'assets/mascots/svg/{n}-{k}.svg','png':f'assets/mascots/png/{n}-{k}.png'} for n,k,t,cat in VARIANTS]}
(ROOT/'assets/mascot-manifest.json').write_text(json.dumps(meta,indent=2))
(ROOT/'assets/design-tokens.json').write_text(json.dumps({'brand':'figg.','colors':{'violet':'#8B3DFF','violetDark':'#6D2FD1','lilac':'#EAD8FF','ink':'#111111','paper':'#FAFAF8','line':'#E8E5E9'},'type':{'display':'Arial Rounded / Nunito / system-ui','body':'Inter / system-ui'},'radii':{'sm':12,'md':24,'lg':36,'xl':54}},indent=2))
# transparent PNGs use alpha. Also generate two preview composited examples
for key,name in [('01-classic','01-classic'),('02-wink','02-wink'),('13-heart','13-heart')]:
    pass
print('ASSETS',len(list(SVGD.glob('*.svg'))),'SVG variants',len(list(PNGD.glob('*.png'))),'PNG variants')
print('BYTES',sum(x.stat().st_size for x in ROOT.rglob('*') if x.is_file()))
