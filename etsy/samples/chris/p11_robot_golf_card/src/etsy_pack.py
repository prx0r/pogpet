from PIL import Image, ImageDraw, ImageFont, ImageFilter
import glob
B="chris/billions/"; O=B+"etsy/"
IF=sorted(glob.glob("etsy_samples/listings/inter/**/*.ttf",recursive=True))
def inter(w,s):
    c=[f for f in IF if w in f.split('/')[-1] and 'Italic' not in f] or IF
    return ImageFont.truetype(c[0],s)
SER="/usr/share/fonts/opentype/urw-base35/P052-"
BG=(236,232,224); NAVY=(27,40,72); INK=(60,64,72)
fr=Image.open(B+"front.png").convert("RGB"); ins=Image.open(B+"inside_r2.png").convert("RGB"); bk=Image.open(B+"back_r2.png").convert("RGB")
def canvas(): 
    c=Image.new("RGB",(2000,2000),BG); return c
def place(c,im,x,y,w):
    im=im.resize((w,int(w*im.height/im.width)),Image.LANCZOS)
    sh=Image.new("L",(im.width+120,im.height+120),0); ImageDraw.Draw(sh).rectangle([60,60,60+im.width,60+im.height],fill=110)
    sh=sh.filter(ImageFilter.GaussianBlur(28)); c.paste((120,110,95),(x-60+18,y-60+26),sh); c.paste(im,(x,y)); return im
c=canvas(); place(c,fr,(2000-1150)//2,(2000-1610)//2,1150); c.save(O+"01_hero.jpg",quality=92)
c=canvas(); place(c,ins,(2000-1820)//2,(2000-1274)//2,1820); c.save(O+"02_inside.jpg",quality=92)
c=canvas(); place(c,fr,150,330,780); place(c,bk,1070,330,780); c.save(O+"03_front_back.jpg",quality=92)
c=fr.crop((830,180,1500,850)).resize((2000,2000),Image.LANCZOS); c.save(O+"04_detail.jpg",quality=92)
c=canvas(); d=ImageDraw.Draw(c)
d.text((160,170),"Your dad, illustrated.",font=ImageFont.truetype(SER+"Bold.otf",110),fill=NAVY)
d.text((160,320),"Beating the robots at golf.",font=ImageFont.truetype(SER+"Italic.otf",80),fill=INK)
rows=[("Size","5 x 7 in (127 x 178 mm), folded"),("Front","Hand-painted style portrait from your photo"),("Caption","Ours, or your own line"),("Inside","Your message, typeset, with a golf vignette"),("Made","To order, from your photo")]
y=560
for k,v in rows:
    d.text((160,y),k.upper(),font=inter("SemiBold",40) ,fill=(118,148,108)); d.text((560,y-6),v,font=inter("Regular",48),fill=INK); y+=150
place(c,fr,1500,1560,330) if False else None
c.save(O+"05_spec.jpg",quality=92)
