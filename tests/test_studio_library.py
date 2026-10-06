"""Real SQLite, owner isolation and subject switching; storage alone is faked."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from test_cards import CardsJourney
from backend import db, studio_library, guide


class StudioLibrary(CardsJourney):
    # Inherit fixture helpers but do not repeat the card render suite here.
    def test_group_photo_links_two_people_and_mesh_needs_assignment(self):
        dad=self.post('/studio/subjects',{'name':'Dad'}).json['subject']['id']
        mum=self.post('/studio/subjects',{'name':'Mum'}).json['subject']['id']
        pid=self.upload()
        self.assertEqual(self.post('/studio/photos/'+pid,{'faces':[{'box':[.1,.1,.2,.2]},{'box':[.5,.1,.2,.2]}]}).status_code,200)
        faces=self.get('/studio/library').json['photos'][0]['faces']
        self.post('/studio/photos/'+pid,{'subjects':[{'subject_id':dad,'face_id':faces[0]['id']},{'subject_id':mum,'face_id':faces[1]['id']}]})
        with db.connect() as c:
            c.execute("INSERT INTO meshes(id,photo_id,status,created_at,updated_at) VALUES (?,?, 'succeeded',0,0)",('mesh_dad',pid));c.commit()
        result=self.get('/studio/library').json
        self.assertEqual(len(result['subjects']),2)
        self.assertEqual({l['subject_id'] for l in result['photos'][0]['subjects']},{dad,mum})
        self.assertEqual(result['meshes'][0]['subject_id'],'')
        self.post('/studio/meshes/mesh_dad/subject',{'subject_id':dad})
        self.assertEqual(self.get('/studio/library').json['meshes'][0]['subject_id'],dad)
        self.assertEqual(self.post('/studio/selection',{'subject_id':mum,'mesh_id':'mesh_dad'}).status_code,400)
        self.assertEqual(self.post('/studio/selection',{'subject_id':dad,'mesh_id':'mesh_dad'}).status_code,200)
        self.post('/studio/selection',{'subject_id':mum,'mesh_id':''})
        with db.connect() as c:self.assertEqual(db.get_profile(c,self.owner)['active_mesh_id'],'')

    def test_subjects_without_meshes_and_foreign_assets_denied(self):
        sid=self.post('/studio/subjects',{'name':'Dad'}).json['subject']['id'];pid=self.upload()
        self.post('/studio/photos/'+pid,{'subjects':[{'subject_id':sid}]})
        self.assertEqual(self.get('/studio/library').json['meshes'],[])
        self.assertEqual(self.get('/studio/library',owner='other').status_code,403)
        self.assertEqual(self.get('/studio/photos/'+pid+'/image',owner='other').status_code,403)
        headers={'X-API-Token':self.headers['X-API-Token'],'X-Owner-Sig':__import__('backend.config',fromlist=['sign_owner']).sign_owner('other')}
        response=self.client.post('/api/studio/photos/'+pid,json={'owner':'other','subjects':[{'subject_id':sid}]},headers=headers)
        self.assertEqual(response.status_code,404)

    def test_detection_validation_and_confirmation_survive_retry(self):
        sid=self.post('/studio/subjects',{'name':'Dad'}).json['subject']['id'];pid=self.upload()
        bad=self.post('/studio/photos/'+pid,{'faces':[{'box':[.9,0,.5,.4]}]})
        self.assertEqual(bad.status_code,400)
        self.post('/studio/photos/'+pid,{'faces':[{'box':[.1,.2,.3,.4]}]})
        face=self.get('/studio/library').json['photos'][0]['faces'][0]
        self.post('/studio/photos/'+pid,{'subjects':[{'subject_id':sid,'face_id':face['id']}],'favourite':True,'tags':['portrait']})
        self.post('/studio/photos/'+pid,{'faces':[{'box':[.2,.2,.2,.2]}]})
        p=self.get('/studio/library').json['photos'][0]
        self.assertEqual(p['subjects'][0]['face_id'],face['id'])
        self.assertTrue(p['subjects'][0]['confirmed']);self.assertTrue(p['favourite'])
        image=self.client.get('/api/studio/photos/'+pid+'/image',query_string={'owner':self.owner,'size':128,'face_id':face['id']},headers=self.headers)
        self.assertEqual(image.status_code,200);image.close()

    def test_autosort_does_not_merge_conflicting_labels(self):
        a=self.upload(0);b=self.upload(1)
        with db.connect() as c:
            c.execute('UPDATE photos SET person=? WHERE id=?',('Dad',a));c.execute('UPDATE photos SET person=? WHERE id=?',('Mum',b));c.commit()
        r=self.client.post('/api/photos/autosort',query_string={'owner':self.owner},headers=self.headers)
        self.assertEqual({g['person'] for g in r.json['groups']},{'Dad','Mum'})

    def test_legacy_labels_need_review_and_corrections_stick(self):
        pid=self.upload()
        with db.connect() as c:c.execute('UPDATE photos SET person=? WHERE id=?',('Dad',pid));c.commit()
        first=self.get('/studio/library').json
        self.assertFalse(first['photos'][0]['subjects'][0]['confirmed'])
        mum=self.post('/studio/subjects',{'name':'Mum'}).json['subject']['id']
        self.post('/studio/photos/'+pid,{'subjects':[{'subject_id':mum}]})
        result=self.get('/studio/library').json
        self.assertEqual([s['subject_id'] for s in result['photos'][0]['subjects']],[mum])

    def test_account_claim_keeps_subject_links_and_selection(self):
        sid=self.post('/studio/subjects',{'name':'Dad'}).json['subject']['id'];pid=self.upload()
        self.post('/studio/photos/'+pid,{'subjects':[{'subject_id':sid}]})
        self.post('/studio/selection',{'subject_id':sid,'mesh_id':''})
        with db.connect() as c:
            db.claim_assets(c,self.owner,'signed_in');c.commit()
            self.assertEqual(c.execute('SELECT owner FROM studio_subjects WHERE id=?',(sid,)).fetchone()['owner'],'signed_in')
            self.assertEqual(c.execute('SELECT owner FROM photos WHERE id=?',(pid,)).fetchone()['owner'],'signed_in')
            self.assertEqual(c.execute('SELECT subject_id FROM studio_selection WHERE owner=?',('signed_in',)).fetchone()['subject_id'],sid)
            self.assertEqual(c.execute('SELECT subject_id FROM photo_subjects WHERE photo_id=?',(pid,)).fetchone()['subject_id'],sid)
            self.assertIsNone(c.execute('SELECT * FROM studio_selection WHERE owner=?',(self.owner,)).fetchone())

    def test_ready_contract_and_api_404_are_json(self):
        ready=self.client.get('/api/studio/status',headers=self.headers)
        self.assertEqual(ready.status_code,200)
        self.assertEqual(ready.json['contract'],'oddhobb.studio.v2')
        missing=self.client.get('/api/studio/not-a-route',headers=self.headers)
        self.assertEqual(missing.status_code,404)
        self.assertTrue(missing.is_json)
        self.assertEqual(missing.json['error'],'API route unavailable')

    def test_recipient_switch_clears_personal_assets(self):
        s=guide.blank_state();s['recipient']['name']='Dad';s['photo_ids']=['dad-photo'];s['mesh_id']='dad-mesh'
        guide.apply_turn(s,'Now shopping for Mum')
        self.assertEqual(s['photo_ids'],[]);self.assertEqual(s['mesh_id'],'')


# unittest would also collect the inherited render journeys. Keep those in test_cards.
for name in dir(CardsJourney):
    if name.startswith('test_') and name not in StudioLibrary.__dict__:
        setattr(StudioLibrary,name,None)

del CardsJourney
