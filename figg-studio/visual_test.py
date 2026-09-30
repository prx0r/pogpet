from pathlib import Path
import re,base64,mimetypes,json
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parent
ht=(root/'index.html').read_text()
css=(root/'css/style.css').read_text();js=(root/'js/app.js').read_text()
ht=re.sub(r'<link rel="stylesheet" href="css/style.css"\s*/>', '<style>'+css+'</style>', ht)
ht=ht.replace('<script src="js/app.js" defer></script>','<script>'+js+'</script>')
all_assets={}
for p in (root/'assets').rglob('*'):
 if p.is_file() and p.suffix.lower() in ('.svg','.jpg','.png'):
  rel=p.relative_to(root).as_posix(); typ=mimetypes.guess_type(str(p))[0] or 'image/svg+xml'
  all_assets[rel]='data:'+typ+';base64,'+base64.b64encode(p.read_bytes()).decode('ascii')
def replaceimg(m):
 path=m.group(1);return 'src="'+all_assets.get(path,path)+'"'
ht=re.sub(r'src="(assets/[^"]+)"',replaceimg,ht)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--no-proxy-server'])
 for width,height,label in [(1440,960,'desktop'),(390,844,'mobile'),(768,1024,'tablet')]:
  page=b.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(ht,wait_until='load',timeout=30000)
  page.evaluate('''mapping => {window.__assetMap = mapping; document.querySelectorAll('img').forEach(img=>{let path=img.getAttribute('src');if(path && mapping[path])img.src=mapping[path]}); const obs=new MutationObserver(()=>document.querySelectorAll('img').forEach(img=>{let path=img.getAttribute('src');if(path && mapping[path])img.src=mapping[path]}));obs.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['src']});}''',all_assets)
  page.wait_for_timeout(250)
  page.screenshot(path=str(root/f'assets/previews/site-{label}-hero.png'),full_page=False,animations='disabled')
  for name,selector in [('story','#story'),('studio','#studio'),('brand','#brand'),('campaigns','#campaigns'),('references','#references')]:
   if label=='desktop':
    page.locator(selector).scroll_into_view_if_needed();page.wait_for_timeout(180);page.screenshot(path=str(root/f'assets/previews/site-{label}-{name}.png'),full_page=False,animations='disabled')
  print(label,'errors',errors,'count',page.locator('.mascot-card').count(),'widths',page.evaluate('document.documentElement.scrollWidth'),page.evaluate('innerWidth'),'height',page.evaluate('document.documentElement.scrollHeight'))
  if label=='desktop':
   page.locator('button[data-filter="occasions"]').click();print('occasions',page.locator('.mascot-card').count())
   page.locator('button[data-filter="all"]').click();page.locator('button[data-id="14"]').first.click();print('preview',page.locator('#preview-name').inner_text())
   page.locator('button[data-scene="night"]').click();print('scene',page.locator('#studio-preview').get_attribute('class'))
  if label=='mobile':
   page.locator('#menu-toggle').click();print('menu open',page.locator('#mobile-nav').is_visible());page.locator('#mobile-nav a').first.click();print('menu closed',not page.locator('#mobile-nav').is_visible())
  page.close()
 b.close()
