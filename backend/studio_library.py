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


def _box_json(raw):
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) and len(v) == 4 else []
    except (ValueError, TypeError):
        return []


def _has_vec(owner, face_id):
    from backend import faces as _faces
    _faces.ensure_schema()
    with db.connect() as c:
        return bool(c.execute(
            "SELECT 1 FROM face_embeddings WHERE face_id=? AND owner=?",
            (face_id, owner)).fetchone())


def _get_vec(owner, face_id):
    import struct as _st
    from backend import faces as _faces
    _faces.ensure_schema()
    with db.connect() as c:
        r = c.execute(
            "SELECT vec, dim FROM face_embeddings WHERE face_id=? AND owner=?",
            (face_id, owner)).fetchone()
    if not r:
        return None
    try:
        return list(_st.unpack(f"{r['dim']}f", r["vec"]))
    except Exception:
        return None


def _embed_missing(owner, pid, rows):
    """Compute+store embeddings for faces lacking them (owner's own photo)."""
    from backend import faces as _faces
    from backend import pipeline as _pipeline
    with db.connect() as c:
        p = c.execute("SELECT * FROM photos WHERE id=?", (pid,)).fetchone()
    if not p:
        return
    try:
        local = _pipeline._local_photo(dict(p))
    except Exception:
        return
    if not local:
        return
    try:
        import cv2 as _cv2
        bgr = _cv2.imread(str(local))
    except Exception:
        return
    if bgr is None:
        return
    boxes = {tuple(round(float(v), 4) for v in f[:4]): f
             for f in _faces.detect_boxes(bgr)}
    with db.connect() as c:
        for r in rows:
            if _has_vec(owner, r["id"]):
                continue
            try:
                box = json.loads(r["box"])
            except (ValueError, TypeError):
                continue
            key = tuple(round(float(v), 4) for v in box)
            f = boxes.get(key)
            if f is None:
                continue
            vec = _faces.embed_face(bgr, f)
            if vec is not None:
                import struct as _st
                import time as _t
                c.execute(
                    "INSERT INTO face_embeddings"
                    " (face_id,photo_id,owner,model,dim,vec,created_at)"
                    " VALUES (?,?,?,?,?,?,?) ON CONFLICT(face_id) DO UPDATE SET"
                    " vec=excluded.vec, created_at=excluded.created_at",
                    (r["id"], pid, owner, _faces.MODEL, len(vec),
                     _st.pack(f"{len(vec)}f", *[float(v) for v in vec]),
                     _t.time()))
        c.commit()


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
            from backend import subjects as _subjects
            subjects = []
            for r in c.execute('SELECT * FROM studio_subjects WHERE owner=? ORDER BY created_at,id', (owner,)):
                s = dict(r)
                full = _subjects.profile_for(c, owner, s["id"])
                s["relationship"] = full.get("relationship", "")
                s["birthday"] = full.get("birthday", "")
                s["interests"] = (full.get("profile", {}) or {}).get("interests", [])
                subjects.append(s)
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

    @bp.get('/api/studio/subjects')
    def subjects_list():
        """Readable family list: every subject with relationship, birthday,
        interests and photo count. Agents read this; humans see the Studio tab."""
        from backend import subjects as _subjects
        owner = request.studio_owner
        with db.connect() as c:
            out = []
            for row in c.execute('SELECT * FROM studio_subjects WHERE owner=? ORDER BY created_at,id',
                                 (owner,)):
                s = dict(row)
                full = _subjects.profile_for(c, owner, s["id"])
                prof = full.get("profile", {})
                n = c.execute('SELECT COUNT(DISTINCT photo_id) FROM photo_subjects WHERE subject_id=?',
                              (s["id"],)).fetchone()[0]
                out.append({"id": s["id"], "name": s["name"], "kind": s.get("kind", "person"),
                            "relationship": full.get("relationship", ""),
                            "birthday": full.get("birthday", ""),
                            "interests": prof.get("interests", []),
                            "profile": {k: v for k, v in prof.items()
                                        if k in ("notes", "facts", "style")},
                            "photos": n})
        return jsonify(ok=True, subjects=out)

    @bp.post('/api/studio/subjects')
    def subject():
        b=request.get_json(silent=True) or {}; name=str(b.get('name') or '').strip()[:60]
        # Names are optional — the roster renders face emblems. Empty is fine.
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

    @bp.post('/api/studio/subjects/<sid>/profile')
    def subject_profile(sid):
        """Onboard a person: birthday + what they enjoy are the key bits.
        Body: {relationship?, birthday? (MM-DD), interests?[]}. Merges."""
        from backend import subjects as _subjects
        b=request.get_json(silent=True) or {}; owner=request.studio_owner
        with db.connect() as c:
            if not _owned(c,'studio_subjects',sid,owner):
                return jsonify(ok=False,error='Friend not found.'),404
            _subjects.ensure_tables(c)
            interests=b.get('interests')
            if interests is not None and not isinstance(interests,list):
                return jsonify(ok=False,error='interests must be a list'),400
            prof=_subjects.set_profile(c,owner,sid,
                relationship=str(b.get('relationship') or '').strip()[:40],
                birthday=str(b.get('birthday') or '').strip()[:10],
                profile=({"interests":[str(i)[:40] for i in interests[:12]]}
                         if interests is not None else None))
        return jsonify(ok=True,subject_id=sid,relationship=prof.get('relationship',''),
                       birthday=prof.get('birthday',''),
                       interests=(prof.get('profile',{}) or {}).get('interests',[]))

    @bp.get('/api/studio/families')
    def families_list():
        from backend import subjects as _subjects
        owner=request.studio_owner
        with db.connect() as c:
            _subjects.ensure_tables(c)
            out=[_subjects.family_detail(c,owner,f['id'])
                 for f in _subjects.families_for(c,owner)]
        return jsonify(ok=True,families=out)

    @bp.post('/api/studio/families')
    def family_create():
        from backend import subjects as _subjects
        b=request.get_json(silent=True) or {}; owner=request.studio_owner
        name=str(b.get('name') or '').strip()
        if not name:
            return jsonify(ok=False,error='Give the family a name.'),400
        with db.connect() as c:
            _subjects.ensure_tables(c)
            fam=_subjects.create_family(c,owner,name)
        return jsonify(ok=True,family=fam)

    @bp.post('/api/studio/families/<fid>/members')
    def family_add(fid):
        from backend import subjects as _subjects
        b=request.get_json(silent=True) or {}; owner=request.studio_owner
        sid=str(b.get('subject_id') or '')
        if not sid:
            return jsonify(ok=False,error='subject_id is required'),400
        with db.connect() as c:
            _subjects.ensure_tables(c)
            try:
                m=_subjects.add_member(c,owner,fid,sid,str(b.get('role') or ''))
            except KeyError as e:
                return jsonify(ok=False,error=str(e)),404
        return jsonify(ok=True,member=m)

    @bp.delete('/api/studio/families/<fid>/members/<sid>')
    def family_remove(fid,sid):
        from backend import subjects as _subjects
        owner=request.studio_owner
        with db.connect() as c:
            _subjects.ensure_tables(c)
            try:
                _subjects.remove_member(c,owner,fid,sid)
            except KeyError as e:
                return jsonify(ok=False,error=str(e)),404
        return jsonify(ok=True,removed=True)

    @bp.post('/api/studio/confirm-batch')
    def confirm_batch():
        """Dad selected + batch upload → one tap confirms all single-face
        shots as Dad. Multi-face photos return in needs_review (face picker);
        faceless in no_face. Detection is data, this tap is consent."""
        b=request.get_json(silent=True) or {}; owner=request.studio_owner
        sid=str(b.get('subject_id') or '').strip()[:80]
        pids=[str(p)[:80] for p in (b.get('photo_ids') or []) if isinstance(p,str)][:30]
        if not sid or not pids:
            return jsonify(ok=False,error='subject_id and photo_ids are required'),400
        confirmed, needs_review, no_face, missing = [], [], [], []
        with db.connect() as c:
            if not _owned(c,'studio_subjects',sid,owner):
                return jsonify(ok=False,error='Friend not found.'),404
            for pid in pids:
                if not _owned(c,'photos',pid,owner):
                    missing.append(pid); continue
                faces=[dict(f) for f in c.execute('SELECT * FROM photo_faces WHERE photo_id=?',(pid,))]
                if len(faces) == 1:
                    c.execute('INSERT OR IGNORE INTO photo_subjects VALUES (?,?,?,1,?)',
                              (pid,sid,faces[0]['id'],'batch-confirm'))
                    confirmed.append(pid)
                elif len(faces) > 1:
                    needs_review.append(pid)
                else:
                    no_face.append(pid)
            c.commit()
        return jsonify(ok=True,confirmed=confirmed,needs_review=needs_review,
                       no_face=no_face,missing=missing)

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
        import os as _os
        owner=request.studio_owner
        with db.connect() as c:
            items=[]
            for r in c.execute("SELECT * FROM orders WHERE owner=? AND status='pending_checkout' ORDER BY created_at DESC",(owner,)):
                item=dict(r)
                item['label']=r['line'].replace('_',' ')
                item['kind']='product'
                line=r['line']
                views=[]
                for vid,vlabel,fname in (("front","Front","%s-front.png"%line),
                                         ("detail","Detail","%s-hero.png"%line),
                                         ("back","Back","%s-back.png"%line)):
                    if _os.path.exists("data/productimg/prod/"+fname):
                        views.append({"id":vid,"label":vlabel,"url":"/img/prod/"+fname})
                if views:
                    item['views']=views
                # design_id on a product row is a *design* ref, not a card —
                # only keep it when it resolves to a real card design.
                did=item.get('design_id') or ''
                if did and not c.execute("SELECT 1 FROM card_designs WHERE id=?",(did,)).fetchone():
                    item.pop('design_id',None)
                items.append(item)
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='card_orders'").fetchone():
                for r in c.execute("SELECT * FROM card_orders WHERE owner=? AND status IN ('pending_checkout','awaiting_payment') ORDER BY created_at DESC",(owner,)):
                    item=dict(r);spec=json.loads(item.pop('spec'));item['label']=spec.get('headline') or 'Greeting card'
                    item['kind']='card'
                    did=item.get('design_id');rev=item.get('revision')
                    if did and rev:
                        item['views']=[{"id":"front","label":"Front","url":"/api/cards/%s/r%s/preview"%(did,rev)},
                                       {"id":"inside","label":"Inside","url":"/api/cards/%s/r%s/inside"%(did,rev)},
                                       {"id":"back","label":"Back","url":"/api/cards/%s/r%s/back"%(did,rev)}]
                        item['preview']='/api/cards/%s/r%s/triptych'%(did,rev)
                    items.append(item)
            drafts=[]
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='card_designs'").fetchone():
                for r in c.execute("SELECT id,latest FROM card_designs WHERE owner=? ORDER BY updated_at DESC LIMIT 20",(owner,)):
                    did,rev=r["id"],r["latest"]
                    srow=c.execute("SELECT spec FROM card_revisions WHERE design_id=? AND revision=?",(did,rev)).fetchone()
                    spec=json.loads(srow["spec"]) if srow else {}
                    jobs={j["kind"] for j in c.execute("SELECT kind FROM card_jobs WHERE owner=? AND design_id=? AND revision=? AND status='ready'",(owner,did,rev))}
                    d={"design_id":did,"revision":rev,"label":spec.get("headline") or "Greeting card",
                       "template":spec.get("template",""),
                       "preview":("/api/cards/%s/r%s/triptych"%(did,rev) if "spread" in jobs
                                  else ("/api/cards/%s/r%s/preview"%(did,rev) if "preview" in jobs else None)),
                       "views":[{"id":"front","label":"Front","url":"/api/cards/%s/r%s/preview"%(did,rev)},
                                {"id":"inside","label":"Inside","url":"/api/cards/%s/r%s/inside"%(did,rev)},
                                {"id":"back","label":"Back","url":"/api/cards/%s/r%s/back"%(did,rev)}] if "preview" in jobs else [],
                       "export_ready":"export" in jobs,"spread_ready":"spread" in jobs}
                    drafts.append(d)
        return jsonify(ok=True,items=items,drafts=drafts,currency='GBP')

    @bp.post('/api/studio/basket/update')
    def basket_update():
        """Remove a reservation or change its qty. Owner-scoped by row —
        one account can never touch another's basket."""
        owner=request.studio_owner
        b=request.get_json(silent=True) or {}
        iid=str(b.get("id") or "")
        action=str(b.get("action") or "remove")
        if not iid:
            return jsonify(ok=False,error="id is required"),400
        with db.connect() as c:
            if action=="remove":
                c.execute("DELETE FROM orders WHERE id=? AND owner=? AND status='pending_checkout'",(iid,owner))
                if c.execute("SELECT 1 FROM sqlite_master WHERE name='card_orders'").fetchone():
                    c.execute("DELETE FROM card_orders WHERE id=? AND owner=? AND status IN ('pending_checkout','awaiting_payment') AND (prodigi_ref IS NULL OR prodigi_ref='')",(iid,owner))
                c.commit()
                return jsonify(ok=True,removed=bool(c.total_changes))
            if action=="qty":
                try: q=max(1,int(b.get("qty") or 1))
                except (ValueError,TypeError): return jsonify(ok=False,error="qty must be a number"),400
                c.execute("UPDATE orders SET qty=? WHERE id=? AND owner=? AND status='pending_checkout'",(q,iid,owner))
                hit=c.total_changes
                if c.execute("SELECT 1 FROM sqlite_master WHERE name='card_orders'").fetchone():
                    c.execute("UPDATE card_orders SET qty=? WHERE id=? AND owner=? AND status IN ('pending_checkout','awaiting_payment')",(q,iid,owner))
                    hit+=c.total_changes
                c.commit()
                return jsonify(ok=True,updated=bool(hit),qty=q)
            return jsonify(ok=False,error="action must be remove or qty"),400

    @bp.get('/api/studio/faces/suggest')
    def faces_suggest():
        """Who is this? Per-face identity suggestions for one photo.

        Query: ?photo_id=<pid>. Suggest-only: scores + ranked subjects,
        never auto-confirms (user confirm writes photo_subjects as today).
        Missing embeddings are computed inline (owner's own photo) so the
        endpoint is self-healing after the backfill.
        """
        from backend import faces as _faces
        owner = request.studio_owner
        pid = (request.args.get("photo_id") or "").strip()
        if not pid:
            return jsonify(ok=False, error="photo_id is required"), 400
        with db.connect() as c:
            p = _owned(c, 'photos', pid, owner)
            if not p:
                return jsonify(ok=False, error="Photo not found."), 404
            _faces.ensure_schema()
            rows = [dict(r) for r in c.execute(
                "SELECT * FROM photo_faces WHERE photo_id=?", (pid,))]
        out = []
        vecs = {}
        if rows and any(not _has_vec(owner, r["id"]) for r in rows):
            _embed_missing(owner, pid, rows)
        for r in rows:
            vec = _get_vec(owner, r["id"])
            if vec is None:
                out.append({"face_id": r["id"], "box": _box_json(r["box"]),
                            "suggestions": [], "strong": False,
                            "new_person": False, "unreadable": True})
                continue
            vecs[r["id"]] = vec
            s = _faces.suggest(vec, owner, exclude_photo=pid)
            out.append({"face_id": r["id"], "box": _box_json(r["box"]), **s})
        return jsonify(ok=True, photo_id=pid, faces=out)

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
