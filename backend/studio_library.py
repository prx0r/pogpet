"""Owner-scoped people and reusable photos, independent of generated meshes.

Detection boxes are suggestions. Identity links are explicitly confirmed by
the customer; a perceptual image hash is never used as a person identifier.
"""
import json
import math
import re
import time

from flask import Blueprint, jsonify, request, send_file
from PIL import Image, ImageOps

from . import config, db, storage

SCHEMA = """
CREATE TABLE IF NOT EXISTS studio_subjects (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL,
 kind TEXT NOT NULL DEFAULT 'person', created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS studio_subject_owner ON studio_subjects(owner);
CREATE TABLE IF NOT EXISTS photo_faces (
 id TEXT PRIMARY KEY, photo_id TEXT NOT NULL REFERENCES photos(id),
 box TEXT NOT NULL, score REAL NOT NULL DEFAULT 0, source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS photo_subjects (
 photo_id TEXT NOT NULL REFERENCES photos(id),
 subject_id TEXT NOT NULL REFERENCES studio_subjects(id),
 face_id TEXT NOT NULL DEFAULT '', confirmed INTEGER NOT NULL DEFAULT 0,
 provenance TEXT NOT NULL DEFAULT 'user',
 PRIMARY KEY(photo_id,subject_id,face_id)
);
CREATE TABLE IF NOT EXISTS studio_photo_meta (
 photo_id TEXT PRIMARY KEY REFERENCES photos(id), favourite INTEGER DEFAULT 0,
 tags TEXT NOT NULL DEFAULT '[]', detection_status TEXT DEFAULT 'pending'
);
CREATE TABLE IF NOT EXISTS mesh_subjects (
 mesh_id TEXT PRIMARY KEY REFERENCES meshes(id),
 subject_id TEXT NOT NULL REFERENCES studio_subjects(id)
);
CREATE TABLE IF NOT EXISTS studio_selection (
 owner TEXT PRIMARY KEY, subject_id TEXT NOT NULL DEFAULT '',
 mesh_id TEXT NOT NULL DEFAULT ''
);
"""


def init():
    with db.connect() as c:
        c.executescript(SCHEMA)


def _owned(c, table, ident, owner):
    if table == 'meshes':
        return c.execute('SELECT m.* FROM meshes m JOIN photos p ON p.id=m.photo_id WHERE m.id=? AND p.owner=?', (ident, owner)).fetchone()
    return c.execute(f'SELECT * FROM {table} WHERE id=? AND owner=?', (ident, owner)).fetchone()


def _box(value):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError('Face box must contain left, top, width and height.')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError('Invalid face coordinates.')
    x, y, w, h = value
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x+w > 1.001 or y+h > 1.001:
        raise ValueError('Face box must fit inside the photo.')
    return value


def _legacy(c, owner):
    """Import old named groups once as review suggestions, not identities."""
    for p in c.execute('SELECT id,person FROM photos WHERE owner=? AND person IS NOT NULL', (owner,)).fetchall():
        name = (p['person'] or '').strip()
        if not name or re.fullmatch(r'Person\s+\d+', name, re.I):
            continue
        s = c.execute('SELECT id FROM studio_subjects WHERE owner=? AND name=?', (owner, name)).fetchone()
        sid = s['id'] if s else db.new_id('person')
        if not s:
            c.execute('INSERT INTO studio_subjects VALUES (?,?,?,?,?)', (sid, owner, name, 'person', time.time()))
        # Do not re-add an old label if the customer has already corrected it.
        if not c.execute('SELECT 1 FROM studio_photo_meta WHERE photo_id=?', (p['id'],)).fetchone():
            c.execute('INSERT OR IGNORE INTO photo_subjects VALUES (?,?,?,0,?)', (p['id'], sid, '', 'legacy-review'))
    c.commit()


def register(app, owner_denied):
    bp = Blueprint('studio_library', __name__)

    @bp.before_request
    def authorize():
        # The service gate still applies; no shopper data is exposed by readiness.
        if request.path == '/api/studio/status':
            return None
        b = request.get_json(silent=True) or {}
        owner = str(request.args.get('owner') or b.get('owner') or '').strip()[:80]
        if not owner:
            # keyed callers omit owner: derive it from their API key
            key = request.headers.get("X-API-Key", "").strip()
            if not key:
                auth = request.headers.get("Authorization", "")
                if auth.lower().startswith("bearer "):
                    key = auth[7:].strip()
            if key:
                with db.connect() as c:
                    u = db.get_user_by_api_key(c, key)
                    a = db.get_agent_by_key(c, key) if not u else None
                owner = (u["handle"] if u else a["agent_handle"] if a else "")
        if not owner:
            return jsonify(ok=False, error='owner is required'), 400
        denied = owner_denied(owner)
        if denied is not None:
            return denied
        request.studio_owner = owner
        init()

    @bp.get('/api/studio/status')
    def status():
        return jsonify(ok=True, contract='oddhobb.studio.v2',
                       features=['subjects', 'photo_faces', 'mesh_subjects', 'basket'])

    @bp.get('/api/studio/library')
    def library():
        owner = request.studio_owner
        with db.connect() as c:
            _legacy(c, owner)
            subjects = [dict(r) for r in c.execute('SELECT * FROM studio_subjects WHERE owner=? ORDER BY created_at,id', (owner,))]
            photos = []
            for row in c.execute('SELECT * FROM photos WHERE owner=? ORDER BY created_at DESC LIMIT 500', (owner,)):
                p = dict(row); pid = p['id']
                p['faces'] = [{**dict(f), 'box': json.loads(f['box'])} for f in c.execute('SELECT * FROM photo_faces WHERE photo_id=?', (pid,))]
                p['subjects'] = [dict(r) for r in c.execute('SELECT ps.* FROM photo_subjects ps JOIN studio_subjects s ON s.id=ps.subject_id WHERE ps.photo_id=? AND s.owner=?', (pid,owner))]
                meta = c.execute('SELECT * FROM studio_photo_meta WHERE photo_id=?', (pid,)).fetchone()
                p.update(dict(meta) if meta else {'favourite': False, 'tags': '[]', 'detection_status': 'pending'})
                p['tags'] = json.loads(p['tags']); p['url'] = f'/api/studio/photos/{pid}/image'
                p['thumbnail_url'] = f'/api/studio/photos/{pid}/image?size=480'
                photos.append(p)
            meshes = []
            for row in c.execute('SELECT m.* FROM meshes m JOIN photos p ON p.id=m.photo_id WHERE p.owner=?', (owner,)):
                m = dict(row)
                explicit = c.execute('SELECT ms.subject_id FROM mesh_subjects ms JOIN studio_subjects s ON s.id=ms.subject_id WHERE ms.mesh_id=? AND s.owner=?', (m['id'],owner)).fetchone()
                # A group photo cannot establish whose head the mesh represents.
                links = c.execute('SELECT DISTINCT subject_id FROM photo_subjects WHERE photo_id=? AND confirmed=1', (m['photo_id'],)).fetchall()
                face_count=c.execute('SELECT count(*) FROM photo_faces WHERE photo_id=?',(m['photo_id'],)).fetchone()[0]
                m['subject_id'] = explicit['subject_id'] if explicit else (links[0]['subject_id'] if len(links)==1 and face_count<=1 else '')
                meshes.append(m)
            selected = c.execute('SELECT * FROM studio_selection WHERE owner=?', (owner,)).fetchone()
        return jsonify(ok=True, subjects=subjects, photos=photos, meshes=meshes, selection=dict(selected) if selected else {})

    @bp.post('/api/studio/subjects')
    def subject():
        b=request.get_json(silent=True) or {}; name=str(b.get('name') or '').strip()[:60]
        if not name:
            return jsonify(ok=False,error='Give your friend a name.'),400
        with db.connect() as c:
            sid=b.get('id') or db.new_id('person')
            if b.get('id'):
                if not _owned(c,'studio_subjects',sid,request.studio_owner):
                    return jsonify(ok=False,error='Friend not found.'),404
                c.execute('UPDATE studio_subjects SET name=? WHERE id=?',(name,sid))
            else:
                kind='pet' if b.get('kind')=='pet' else 'person'
                c.execute('INSERT INTO studio_subjects VALUES (?,?,?,?,?)',(sid,request.studio_owner,name,kind,time.time()))
            c.commit()
        return jsonify(ok=True,subject={'id':sid,'name':name})

    @bp.post('/api/studio/photos/<pid>')
    def annotate(pid):
        b=request.get_json(silent=True) or {}; owner=request.studio_owner
        try:
            with db.connect() as c:
                if not _owned(c,'photos',pid,owner):
                    return jsonify(ok=False,error='Photo not found.'),404
                links=b.get('subjects')
                if links is not None:
                    if not isinstance(links,list) or len(links)>30: raise ValueError('Invalid subject list.')
                    for link in links:
                        if not isinstance(link,dict) or not _owned(c,'studio_subjects',link.get('subject_id'),owner): raise ValueError('Friend not found.')
                        fid=link.get('face_id') or ''
                        if fid and not c.execute('SELECT 1 FROM photo_faces WHERE id=? AND photo_id=?',(fid,pid)).fetchone(): raise ValueError('Face does not belong to this photo.')
                if 'faces' in b:
                    faces=b['faces']
                    if not isinstance(faces,list) or len(faces)>30: raise ValueError('Invalid detections.')
                    boxes=[_box(f.get('box')) for f in faces if isinstance(f,dict)]
                    if len(boxes)!=len(faces): raise ValueError('Invalid detections.')
                c.execute('INSERT OR IGNORE INTO studio_photo_meta(photo_id) VALUES (?)',(pid,))
                if 'faces' in b:
                    # Do not invalidate an identity the customer already confirmed.
                    if not c.execute("SELECT 1 FROM photo_faces WHERE photo_id=?",(pid,)).fetchone():
                        for box in boxes:
                            c.execute('INSERT INTO photo_faces VALUES (?,?,?,?,?)',(db.new_id('face'),pid,json.dumps(box),0,'mediapipe'))
                    c.execute('UPDATE studio_photo_meta SET detection_status=? WHERE photo_id=?',('ready' if boxes else 'no_faces',pid))
                if 'favourite' in b: c.execute('UPDATE studio_photo_meta SET favourite=? WHERE photo_id=?',(int(bool(b['favourite'])),pid))
                if 'tags' in b:
                    tags=b['tags']
                    if not isinstance(tags,list) or len(tags)>20 or any(not isinstance(t,str) or len(t)>40 for t in tags): raise ValueError('Invalid photo tags.')
                    c.execute('UPDATE studio_photo_meta SET tags=? WHERE photo_id=?',(json.dumps(tags),pid))
                if links is not None:
                    c.execute('DELETE FROM photo_subjects WHERE photo_id=?',(pid,))
                    for link in links:
                        c.execute('INSERT OR IGNORE INTO photo_subjects VALUES (?,?,?,1,?)',(pid,link['subject_id'],link.get('face_id') or '', 'user-confirmed'))
                    # Legacy single-label consumers get a name only for a single subject.
                    names=[r['name'] for r in c.execute('SELECT DISTINCT s.name FROM photo_subjects ps JOIN studio_subjects s ON s.id=ps.subject_id WHERE ps.photo_id=?',(pid,))]
                    c.execute('UPDATE photos SET person=? WHERE id=?',(names[0] if len(names)==1 else None,pid))
                c.commit()
                linked=[dict(r) for r in c.execute('SELECT ps.subject_id,ps.face_id,ps.confirmed,s.name FROM photo_subjects ps JOIN studio_subjects s ON s.id=ps.subject_id WHERE ps.photo_id=?',(pid,))]
        except (ValueError,TypeError,AttributeError) as e:
            return jsonify(ok=False,error=str(e)),400
        return jsonify(ok=True,linked=linked)

    @bp.post('/api/studio/meshes/<mid>/subject')
    def mesh_subject(mid):
        sid=(request.get_json(silent=True) or {}).get('subject_id')
        with db.connect() as c:
            if not _owned(c,'meshes',mid,request.studio_owner) or not _owned(c,'studio_subjects',sid,request.studio_owner):
                return jsonify(ok=False,error='Mesh or friend not found.'),404
            c.execute('INSERT OR REPLACE INTO mesh_subjects VALUES (?,?)',(mid,sid));c.commit()
        return jsonify(ok=True)

    @bp.post('/api/studio/selection')
    def selection():
        b=request.get_json(silent=True) or {}; sid=b.get('subject_id') or ''; mid=b.get('mesh_id') or '';owner=request.studio_owner
        with db.connect() as c:
            if sid and not _owned(c,'studio_subjects',sid,owner): return jsonify(ok=False,error='Friend not found.'),404
            if mid:
                m=_owned(c,'meshes',mid,owner)
                explicit=c.execute('SELECT subject_id FROM mesh_subjects WHERE mesh_id=?',(mid,)).fetchone()
                links=c.execute('SELECT DISTINCT subject_id FROM photo_subjects WHERE photo_id=? AND confirmed=1',(m['photo_id'],)).fetchall() if m else []
                face_count=c.execute('SELECT count(*) FROM photo_faces WHERE photo_id=?',(m['photo_id'],)).fetchone()[0] if m else 0
                belongs=explicit['subject_id']==sid if explicit else len(links)==1 and face_count<=1 and links[0]['subject_id']==sid
                if not m or not belongs: return jsonify(ok=False,error='That mesh is not assigned to this friend.'),400
            c.execute('INSERT OR REPLACE INTO studio_selection VALUES (?,?,?)',(owner,sid,mid))
            db.set_active(c,owner,mid);c.commit()
        return jsonify(ok=True,subject_id=sid,mesh_id=mid)

    @bp.get('/api/studio/basket')
    def basket():
        owner=request.studio_owner
        with db.connect() as c:
            items=[{**dict(r),'label':r['line'].replace('_',' ')} for r in c.execute("SELECT * FROM orders WHERE owner=? AND status='pending_checkout' ORDER BY created_at DESC",(owner,))]
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='card_orders'").fetchone():
                for r in c.execute("SELECT * FROM card_orders WHERE owner=? AND status='pending_checkout' ORDER BY created_at DESC",(owner,)):
                    item=dict(r);spec=json.loads(item.pop('spec'));item['label']=spec.get('headline') or 'Greeting card';items.append(item)
        return jsonify(ok=True,items=items,currency='GBP')

    @bp.get('/api/studio/photos/<pid>/image')
    def image(pid):
        with db.connect() as c: p=_owned(c,'photos',pid,request.studio_owner)
        if not p: return jsonify(ok=False,error='Photo not found.'),404
        path=config.LOCAL_TMP / ('studio_'+p['sha256']+'.jpg')
        try:
            if not path.exists(): storage.get(p['r2_key'],path)
            size=request.args.get('size')
            face_id=request.args.get('face_id')
            face=None
            if face_id:
                with db.connect() as c: face=c.execute('SELECT box FROM photo_faces WHERE id=? AND photo_id=?',(face_id,pid)).fetchone()
                if not face: return jsonify(ok=False,error='Face not found.'),404
            if size:
                size=max(64,min(1200,int(size)));thumb=path.with_name(path.stem+f'_{size}_'+(face_id or 'full')+'.jpg')
                if not thumb.exists():
                    with Image.open(path) as im:
                        im=ImageOps.exif_transpose(im).convert('RGB')
                        if face:
                            x,y,w,h=json.loads(face['box']);margin=.3
                            im=im.crop((max(0,(x-w*margin)*im.width),max(0,(y-h*margin)*im.height),min(im.width,(x+w*(1+margin))*im.width),min(im.height,(y+h*(1+margin))*im.height)))
                        im.thumbnail((size,size));im.save(thumb,'JPEG',quality=85)
                path=thumb
            response=send_file(path,mimetype='image/jpeg')
            response.headers['Cache-Control']='private, max-age=3600'
            return response
        except (ValueError,OSError,storage.StorageError):
            return jsonify(ok=False,error='Photo could not be loaded.'),400

    app.register_blueprint(bp)
