import asyncio, glob, os, sys, subprocess
from playwright.async_api import async_playwright
DUR={'01':2.4,'02':1.0,'03':1.4,'04':1.6,'05':1.6,'06':1.6,'07':3.0,'08':2.0,'09':1.8}
os.makedirs('gif',exist_ok=True)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        pg=await b.new_page(viewport={'width':240,'height':240})
        items=sorted(glob.glob('0*.svg'))+['09-css-3d-coin.html']
        only=sys.argv[1:]
        for f in items:
            k=f[:2]
            if only and k not in only: continue
            src=open(f).read().replace('width="160" height="160"','width="200" height="200"')
            if f.endswith('.html'): src=src.replace('--s:120px','--s:190px').replace('--t:10px','--t:16px')
            await pg.set_content(f'<html><body style="margin:0;background:#fff;display:grid;place-items:center;height:240px">{src}</body></html>')
            await pg.wait_for_timeout(200)
            d=DUR[k]; n=int(d*25); fr=f'gif/_{k}'; os.makedirs(fr,exist_ok=True)
            for i in range(n):
                t=i/n*d*1000
                await pg.evaluate(f'document.getAnimations().forEach(a=>{{a.pause();a.currentTime={t}}})')
                await pg.screenshot(path=f'{fr}/{i:03d}.png')
            name=f[:-4] if f.endswith('.svg') else f[:-5]
            subprocess.run(f'ffmpeg -y -loglevel error -framerate 25 -i {fr}/%03d.png -vf "split[a][b];[a]palettegen=max_colors=64[p];[b][p]paletteuse" -loop 0 gif/{name}.gif',shell=True)
            print('gif',name,n)
        await b.close()
asyncio.run(main())
