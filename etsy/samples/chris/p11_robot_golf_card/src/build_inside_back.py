from PIL import Image, ImageDraw, ImageFont, ImageChops
FD="/usr/share/fonts/opentype/urw-base35/"
f=lambda n,s: ImageFont.truetype(FD+n,s)
NAVY=(27,40,72); GREEN=(118,148,108); INK=(52,58,72)
src=Image.open("inside_stencil.png").convert("RGB")  # 1232x864
S=3000/1232
right=src.crop((640,0,1232,864)).resize((1500-0,2100),Image.LANCZOS)  # clean paper
ins=Image.new("RGB",(3000,2100)); ins.paste(right.transpose(Image.FLIP_LEFT_RIGHT),(0,0)); ins.paste(right,(1500,0))
d=ImageDraw.Draw(ins); d.line([(1500,0),(1500,2100)],fill=(232,226,205),width=3)
# stencil: crop, mask out paper
st=src.crop((95,205,535,655)); bg=Image.new("RGB",st.size,src.getpixel((30,30)))
diff=ImageChops.difference(st,bg).convert("L").point(lambda v:255 if v>28 else 0)
w=470; st=st.resize((w,int(w*st.height/st.width)),Image.LANCZOS); m=diff.resize(st.size,Image.LANCZOS)
ins.paste(st,(750-w//2,1050-st.height//2-40),m)
# small elegant rule under stencil
d.line([(690,1050+st.height//2+30),(810,1050+st.height//2+30)],fill=GREEN,width=3)
# right page typography
def ctr(t,font,y,fill):
    tw=d.textlength(t,font=font); d.text((2250-tw/2,y),t,font=font,fill=fill)
ctr("Dear Dad,",f("P052-Italic.otf",112),300,NAVY)
d.line([(2205,480),(2295,480)],fill=GREEN,width=3)
ctr("Happy Birthday",f("P052-Bold.otf",128),760,NAVY)
ctr("& Happy Retirement",f("P052-Bold.otf",96),920,NAVY)
d.line([(2130,1090),(2370,1090)],fill=GREEN,width=4)
body=f("P052-Roman.otf",66)
for i,l in enumerate(["Hope you enjoy every minute of it,","and hopefully see you soon!"]): ctr(l,body,1170+i*92,INK)
ctr("Lots of love,",f("P052-Italic.otf",80),1620,INK)
ctr("Tom",f("P052-BoldItalic.otf",120),1720,NAVY)
ins.save("inside_r2.png")
back=Image.new("RGB",(1500,2100)); back.paste(right,(0,0)); bd=ImageDraw.Draw(back)
t="oddhobb.com"; fo=f("P052-Roman.otf",48); tw=bd.textlength(t,font=fo); bd.text(((1500-tw)/2,1880),t,font=fo,fill=INK)
back.save("back_r2.png")
q=Image.new("RGB",(4500,2100)); q.paste(ins,(0,0)); q.paste(back,(3000,0)); q.resize((1500,700)).save("/tmp/r2q.png")
