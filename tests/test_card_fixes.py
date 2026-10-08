"""Regression tests for the peer-review findings; no external services."""
import ast
import asyncio
import importlib.util
import io
import json
import os
import shutil
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import test_cards as journey
from backend import cards,card_scenes,config,db,storage,server
from PIL import Image


class CardFixes(unittest.TestCase):
    setUp=journey.CardsJourney.setUp
    tearDown=journey.CardsJourney.tearDown
    upload=journey.CardsJourney.upload
    design=journey.CardsJourney.design
    render=journey.CardsJourney.render
    get=journey.CardsJourney.get
    post=journey.CardsJourney.post

    def signup(self,handle='claimedcards',headers=None):
        server._AUTH_FAILS.clear()
        return self.client.post('/api/accounts',json={'handle':handle,'password':'test-password-123','claim_owner':self.owner},headers=headers or self.headers)

    def test_signup_keeps_cutout_revisions_outputs_and_reservation(self):
        pid=self.upload();b=io.BytesIO();Image.new('RGBA',(500,600),(20,50,100,180)).save(b,'PNG')
        with patch('premesh.normalize',return_value=SimpleNamespace(ok=True,data=b.getvalue())):
            cut=self.post('/cards/cutouts',{'photo_id':pid,'crop':[0,0,1,1]}).json['cutout_id']
        x=self.design([pid]);x['spec']['photos'][0]['cutout']=cut
        x=self.post('/cards/designs',{'id':x['id'],'expected_revision':1,'spec':x['spec']}).json['design']
        jobs=[self.render(x,k) for k in ('preview','export','motion')]
        originals=[self.get(j['url'][4:]).data for j in jobs]
        order_body={'revision':x['revision'],'qty':1,'idempotency_key':'claim-reservation-123'}
        before=self.post('/cards/'+x['id']+'/order',order_body).json['order']
        old_key=cards.key(self.owner,x['id'],x['revision'],'export')
        with patch.object(storage,'claim_owner') as move:
            r=self.signup()
            self.assertEqual(r.status_code,200,r.json)
            move.assert_called_once_with(self.owner,'claimedcards',preserve_photos=True)
        self.assertEqual(r.json['claimed']['card_orders'],1)
        headers={'X-API-Token':config.API_TOKEN,'X-API-Key':r.json['api_key']}
        def get(path):return self.client.get('/api'+path,query_string={'owner':'claimedcards'},headers=headers,buffered=True)
        self.assertEqual(len(get('/cards/designs').json['designs']),1)
        self.assertEqual(cards.key('claimedcards',x['id'],x['revision'],'export'),old_key)
        self.assertEqual(self.client.get('/api/artifacts/'+old_key,headers=self.headers).status_code,403)
        shutil.rmtree(config.DATA/'cards/cache')
        for j,raw in zip(jobs,originals):
            response=get(j['url'][4:]);self.assertEqual(response.status_code,200);self.assertEqual(response.data,raw);response.close()
        self.assertEqual(get('/cards/cutouts/'+cut+'/image').status_code,200)
        reused=self.client.post('/api/cards/'+x['id']+'/order',json={'owner':'claimedcards',**order_body},headers=headers)
        self.assertEqual(reused.json['order']['id'],before['id'])
        self.assertEqual(reused.json['order']['export_key'],old_key)
        self.assertEqual(self.get('/cards/designs/'+x['id']).status_code,404)
        edited={**x['spec'],'headline':'After signup'}
        saved=self.client.post('/api/cards/designs',json={'owner':'claimedcards','id':x['id'],'expected_revision':x['revision'],'spec':edited},headers=headers)
        self.assertEqual(saved.status_code,200,saved.json)
        self.owner='claimedcards';self.headers=headers
        self.render(saved.json['design'])

    def test_claim_requires_owner_proof(self):
        self.design(template='typography')
        r=self.signup(headers={'X-API-Token':config.API_TOKEN})
        self.assertEqual(r.status_code,403)
        with db.connect() as c:self.assertIsNone(db.get_user_by_handle(c,'claimedcards'))

    def test_signup_during_render_is_retryable_without_creating_account(self):
        x=self.design(template='typography');started=threading.Event();release=threading.Event();original=card_scenes.front
        def wait(*a,**kw):started.set();release.wait(5);return original(*a,**kw)
        with patch.object(card_scenes,'front',side_effect=wait):
            jid=self.post('/cards/'+x['id']+'/render',{'revision':1}).json['job']['id']
            try:
                self.assertTrue(started.wait(3))
                r=self.signup();self.assertEqual(r.status_code,409,r.json)
                with db.connect() as c:self.assertIsNone(db.get_user_by_handle(c,'claimedcards'))
            finally:
                release.set()
                for _ in range(150):
                    if self.get('/cards/jobs/'+jid).json['job']['status'] in ('ready','failed'):break
                    time.sleep(.02)
        with patch.object(storage,'claim_owner'):
            self.assertEqual(self.signup().status_code,200)

    def test_old_schema_namespace_migrates_and_is_stable(self):
        with db.connect() as c:
            c.execute('DROP TABLE card_designs')
            c.execute('CREATE TABLE card_designs (id TEXT PRIMARY KEY,owner TEXT,latest INTEGER,created_at REAL,updated_at REAL)')
            c.execute('INSERT INTO card_designs VALUES (?,?,?,?,?)',('old-card',self.owner,1,0,0));c.commit()
        cards.init()
        original=cards.key(self.owner,'old-card',1,'preview')
        with db.connect() as c:c.execute("UPDATE card_designs SET owner='newowner'");c.commit()
        self.assertEqual(cards.key('newowner','old-card',1,'preview'),original)

    def test_overflow_fails_render_and_cannot_be_reserved(self):
        # Contract (docs/cardspec.md): over-cap copy is rejected at SAVE, so
        # it can never reach render or reserve. Oversized headline → 400 on
        # save; a design with no export render → 409 on order.
        r = self.post('/cards/designs', {'spec': {'template': 'typography', 'format': '5x7',
                         'photos': [], 'headline': 'a\n' * 79 + 'a', 'recipient': '',
                         'sender': '', 'inside_message': ''}})
        self.assertEqual(r.status_code, 400)
        self.assertIn('headline', r.json['error'])
        x = self.design([self.upload()], headline='ok headline')
        self.assertEqual(self.post('/cards/' + x['id'] + '/order', {'revision': 1, 'qty': 1,
                         'idempotency_key': 'overflow-reserve-123'}).status_code, 409)

    def transport(self,req,timeout=None):
        from urllib.parse import urlsplit
        u=urlsplit(req.full_url);r=self.client.open(u.path+'?'+u.query,method=req.get_method(),data=req.data,headers=dict(req.header_items()))
        if r.status_code>=400:raise urllib.error.HTTPError(req.full_url,r.status_code,'',{},io.BytesIO(r.data))
        return io.BytesIO(r.data)

    def test_mcp_signature_reads_sign_only_configured_owner(self):
        tree=ast.parse(Path('backend/mcp_server.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='_call')
        scope={'asyncio':asyncio,'os':os,'json':json,'API':'http://local','_service_token':lambda:config.API_TOKEN,'_key':lambda:''}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'backend/mcp_server.py','exec'),scope)
        x=self.design(template='typography');job=self.render(x)
        with patch.dict(os.environ,{'FIGG_OWNER':self.owner}),patch.object(urllib.request,'urlopen',side_effect=self.transport):
            for path in ['/cards/designs','/cards/photos','/cards/'+x['id']+'/scene','/cards/jobs/'+job['id']]:
                response=asyncio.run(scope['_call']('GET','/api'+path+'?owner='+self.owner));self.assertTrue(response['ok'],response)
            denied=asyncio.run(scope['_call']('GET','/api/cards/designs?owner=pog_foreign'))
            self.assertFalse(denied['ok'])

    def test_bridge_identity_verification_and_child_env(self):
        spec=importlib.util.spec_from_file_location('test_bridge',Path('bridge/llm_bridge.py'));bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
        with patch.dict(os.environ,{'API_TOKEN':config.API_TOKEN}),patch.object(urllib.request,'urlopen',side_effect=self.transport):
            actor=bridge.verified_actor(self.owner,config.sign_owner(self.owner))
            self.assertEqual(actor['FIGG_OWNER'],self.owner)
            with self.assertRaises(PermissionError):bridge.verified_actor('pog_foreign',config.sign_owner(self.owner))
        cli=config.DATA/'cli.js';cli.write_text('// test')
        with patch.object(bridge,'PI_CLI',cli),patch.dict(os.environ,{'OPENCODE_API_KEY':'local-provider-test','FIGG_API_KEY':'wrong-parent-key'}),patch.object(bridge.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='done',stderr='')) as run:
            self.assertEqual(bridge.run_pi([],100,.8,actor_env=actor),'done')
            self.assertEqual(run.call_args.kwargs['env']['FIGG_OWNER'],self.owner)
            self.assertEqual(run.call_args.kwargs['env']['FIGG_API_KEY'],'')
            self.assertEqual(run.call_args.kwargs['env']['FIGG_OWNER_SIG'],config.sign_owner(self.owner))

    def test_claim_storage_copies_photos_and_keeps_card_paths(self):
        with patch.object(storage.subprocess,'run') as run:
            storage.claim_owner('pog_old','newowner',preserve_photos=True)
        ops=[c.args[0][1] for c in run.call_args_list]
        self.assertEqual(ops,['copy','movetree','movetree'])

if __name__=='__main__':unittest.main()
