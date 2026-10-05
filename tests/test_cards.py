"""Offline customer-journey tests: real SQLite/PIL/ffmpeg, fake R2 only."""
import io
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from backend import cards, card_scenes, config, db, storage
from backend.server import app


class CardsJourney(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.patches=[patch.object(config,'DATA',root),patch.object(config,'DB_PATH',root/'test.db'),patch.object(config,'LOCAL_TMP',root/'tmp'),patch.object(config,'LOCAL_MESH',root/'meshes'),patch.object(config,'UPLOAD_DIR',root/'uploads')]
        self.objects=root/'r2'
        def put(src,k):
            dest=self.objects/k;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);return k
        def get(k,dest):
            src=self.objects/k
            if not src.exists():raise storage.StorageError('missing')
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);return dest
        self.patches += [patch.object(storage,'put',side_effect=put),patch.object(storage,'get',side_effect=get)]
        for p in self.patches:p.start()
        db.init();cards.init()
        self.client=app.test_client()
        self.owner='pog_cardtests'
        self.headers={'X-API-Token':config.API_TOKEN,'X-Owner-Sig':config.sign_owner(self.owner)}

    def tearDown(self):
        # Every queued render in a test is awaited before its temporary DB goes away.
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def post(self,path,body):
        return self.client.post('/api'+path,json={'owner':self.owner,**body},headers=self.headers)

    def get(self,path,owner=None):
        r=self.client.get('/api'+path,query_string={'owner':owner or self.owner},headers=self.headers,buffered=True)
        r.close()
        return r

    def upload(self,n=0):
        img=Image.new('RGB',(800,1000),'#f4e8cd');d=ImageDraw.Draw(img)
        d.rectangle((70+n*12,150,730,850),fill=(50+n*10,80,110));d.ellipse((260,190,540,470),fill='#dfb295')
        b=io.BytesIO();img.save(b,'JPEG');b.seek(0)
        r=self.client.post('/api/photos',data={'owner':self.owner,'photo':(b,f'dad-{n}.jpg')},headers=self.headers)
        self.assertEqual(r.status_code,200,r.json)
        return r.json['photo']['id']

    def design(self,pids=None,template='portrait',**kw):
        s={'template':template,'format':'5x7','headline':'Dad is officially a legend','recipient':'Dad','sender':'Love from all of us','inside_message':'Happy birthday!','photos':[{'photo_id':p,'crop':[0,0,1,1],'focus':[.5,.5]} for p in (pids or [])]}
        s.update(kw)
        r=self.post('/cards/designs',{'spec':s});self.assertEqual(r.status_code,200,r.json);return r.json['design']

    def render(self,x,kind='preview'):
        r=self.post('/cards/'+x['id']+'/render',{'revision':x['revision'],'kind':kind})
        self.assertEqual(r.status_code,200,r.json);job=r.json['job']
        for _ in range(250):
            j=self.get('/cards/jobs/'+job['id']).json['job']
            if j['status'] in ('ready','failed'):break
            time.sleep(.05)
        self.assertEqual(j['status'],'ready',j)
        return j

    def test_shared_scene_manifest_pins_revision_and_private_outputs(self):
        x=self.design(template='typography')
        self.render(x)
        self.render(x,'motion')
        route='/cards/'+x['id']+'/scene'
        scene=self.get(route).json['scene']
        self.assertEqual(scene['version'],'oddhobb.scene.v1')
        self.assertEqual(scene['revision'],x['revision'])
        self.assertEqual(scene['outputs']['motion']['status'],'ready')
        self.assertIn('/r1/motion',scene['outputs']['motion']['url'])
        self.assertFalse(scene['capabilities']['ar'])
        changed={**x['spec'],'headline':'A new headline'}
        y=self.post('/cards/designs',{'id':x['id'],'expected_revision':1,'spec':changed}).json['design']
        self.assertEqual(self.get(route).json['scene']['revision'],y['revision'])
        pinned=self.client.get('/api'+route,query_string={'owner':self.owner,'revision':'1'},headers=self.headers)
        self.assertEqual(pinned.json['scene']['spec']['headline'],x['spec']['headline'])
        self.assertEqual(self.get(route,owner='someone_else').status_code,403)
        bad=self.client.get('/api'+route,query_string={'owner':self.owner,'revision':'nope'},headers=self.headers)
        self.assertEqual(bad.status_code,400)

    def test_five_photos_without_mesh_and_saved_collage(self):
        pids=[self.upload(n) for n in range(5)]
        self.assertEqual(len(self.get('/cards/photos').json['photos']),5)
        x=self.design(pids,'family');j=self.render(x)
        self.assertEqual(self.get('/cards/designs/'+x['id']).json['design']['spec']['photos'][0]['photo_id'],pids[0])
        image=self.get(j['url'].removeprefix('/api')).data
        self.assertTrue(image.startswith(b'\x89PNG'))
        with db.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM meshes').fetchone()[0],0)

    def test_revision_changes_pixels_and_old_artwork_survives(self):
        x=self.design([self.upload()]);a=self.render(x);old=self.get(a['url'][4:]).data
        s=x['spec'];s['headline']='An entirely different headline';s['photos'][0]['crop']=[.2,.1,.6,.8]
        r=self.post('/cards/designs',{'id':x['id'],'expected_revision':1,'spec':s})
        self.assertEqual(r.status_code,200,r.json);y=r.json['design'];self.assertEqual(y['revision'],2)
        b=self.render(y);self.assertNotEqual(old,self.get(b['url'][4:]).data)
        self.assertEqual(old,self.get(a['url'][4:]).data)
        conflict=self.post('/cards/designs',{'id':x['id'],'expected_revision':1,'spec':s});self.assertEqual(conflict.status_code,409)

    def test_foreign_assets_designs_jobs_and_exports_denied(self):
        pid=self.upload();x=self.design([pid]);j=self.render(x)
        for path in ['/cards/photos/'+pid+'/image','/cards/designs/'+x['id'],'/cards/jobs/'+j['id'],j['url'][4:]]:
            self.assertEqual(self.get(path,owner='pog_someoneelse').status_code,403)
        # Even correctly signed second owner cannot use a first owner's photo.
        headers={'X-API-Token':config.API_TOKEN,'X-Owner-Sig':config.sign_owner('pog_other')}
        r=self.client.post('/api/cards/designs',json={'owner':'pog_other','spec':x['spec']},headers=headers)
        self.assertEqual(r.status_code,404)

    def test_typography_export_and_idempotent_card_order(self):
        x=self.design(template='typography');self.render(x,'export')
        b={'revision':1,'qty':2,'idempotency_key':'same-checkout-attempt'}
        a=self.post('/cards/'+x['id']+'/order',b);self.assertEqual(a.status_code,200,a.json)
        second=self.post('/cards/'+x['id']+'/order',b);self.assertEqual(a.json['order']['id'],second.json['order']['id'])
        self.assertEqual(a.json['order']['price_cents'],2000)
        self.assertEqual(json.loads(a.json['order']['spec'])['template'],'typography')
        with db.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM orders').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT count(*) FROM card_orders').fetchone()[0],1)
        bad=self.post('/cards/'+x['id']+'/order',{**b,'qty':3});self.assertEqual(bad.status_code,409)

    @unittest.skipUnless(shutil.which('ffmpeg'),'ffmpeg unavailable')
    def test_matching_mp4_has_real_motion(self):
        x=self.design([self.upload()],'breaking_news');j=self.render(x,'motion')
        raw=self.get(j['url'][4:]).data;self.assertIn(b'ftyp',raw[:40])
        first=card_scenes.front(x['spec'],cards.assets(self.owner,x['spec']),progress=0)
        last=card_scenes.front(x['spec'],cards.assets(self.owner,x['spec']),progress=1)
        self.assertNotEqual(first.tobytes(),last.tobytes())

    def test_cutout_crop_and_provider_failure_keep_original(self):
        pid=self.upload()
        with patch('premesh.normalize',side_effect=__import__('premesh').TransformError('offline')):
            r=self.post('/cards/cutouts',{'photo_id':pid,'crop':[.1,.1,.8,.8]})
        self.assertEqual(r.status_code,502)
        self.assertEqual(self.get('/cards/photos/'+pid+'/image').status_code,200)
        r=self.post('/cards/cutouts',{'photo_id':pid,'crop':[-1,0,1,1]});self.assertEqual(r.status_code,400)

    def test_successful_cutout_reused_and_stale_crop_rejected(self):
        from types import SimpleNamespace
        pid=self.upload();buf=io.BytesIO();Image.new('RGBA',(500,600),(20,50,100,128)).save(buf,'PNG')
        b={'photo_id':pid,'crop':[0,0,1,1]}
        with patch('premesh.normalize',return_value=SimpleNamespace(ok=True,data=buf.getvalue())) as normal:
            a=self.post('/cards/cutouts',b);again=self.post('/cards/cutouts',b)
            self.assertEqual(normal.call_count,1)
        self.assertEqual(a.status_code,200,a.json);self.assertEqual(a.json['cutout_id'],again.json['cutout_id'])
        x=self.design([pid]);s=x['spec'];s['photos'][0]['cutout']=a.json['cutout_id'];s['photos'][0]['crop']=[.1,.1,.8,.8]
        r=self.post('/cards/designs',{'spec':s});self.assertEqual(r.status_code,400)

    def test_failed_render_can_retry_same_revision(self):
        x=self.design(template='typography')
        with patch.object(card_scenes,'front',side_effect=RuntimeError('render unavailable')):
            r=self.post('/cards/'+x['id']+'/render',{'revision':1})
            jid=r.json['job']['id']
            for _ in range(100):
                j=self.get('/cards/jobs/'+jid).json['job']
                if j['status']=='failed':break
                time.sleep(.01)
            self.assertEqual(j['status'],'failed')
        self.render(x)

    def test_invalid_crop_quantity_and_unsigned_access(self):
        x=self.design(template='typography')
        for q in ['two',True,0,21]:
            r=self.post('/cards/'+x['id']+'/order',{'revision':1,'qty':q,'idempotency_key':'bad-quantity-key'});self.assertEqual(r.status_code,400)
        pid=self.upload();s=x['spec'];s.update(template='portrait',photos=[{'photo_id':pid,'crop':[0,0,float('nan'),1]}])
        r=self.post('/cards/designs',{'spec':s});self.assertEqual(r.status_code,400)
        r=self.client.get('/api/cards/photos',query_string={'owner':self.owner},headers={'X-API-Token':config.API_TOKEN})
        self.assertEqual(r.status_code,403)


if __name__=='__main__':unittest.main()
