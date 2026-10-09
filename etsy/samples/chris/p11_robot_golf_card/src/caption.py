from PIL import Image, ImageDraw, ImageFont
import sys
F="/usr/share/fonts/opentype/urw-base35/C059-Bold.otf"
jobs=[("n1.png",None,["The robots couldn't quite","get the hang of it."]),
      ("n2.png",(38,48,826,1172),["Billions of calculations.","Not one birdie."]),
      ("n3.png",None,["Turns out golf","isn't downloadable."])]
for src,crop,lines in jobs:
    im=Image.open(f"chris/robots/{src}").convert("RGB")
    if crop: im=im.crop(crop).resize((864,1216),Image.LANCZOS)
    d=ImageDraw.Draw(im); W=im.width
    size=80
    while True:
        f=ImageFont.truetype(F,size)
        if max(d.textlength(l,font=f) for l in lines)<=W-90: break
        size-=2
    y=48
    for l in lines:
        w=d.textlength(l,font=f); d.text(((W-w)/2,y),l,font=f,fill=(18,18,18)); y+=int(size*1.18)
    im.save(f"chris/robots/captioned/{src.replace('.png','_cap.png')}")
    print(src,size,y)
