"""Offline acceptance run of the canonical card path, on a throwaway DB.

Real photos -> backend YuNet + SFace (photo_faces, face_embeddings) -> tag the
hero -> labels -> cardgen.recommend/cast -> engine.run with pre-generated art
standing in for fal -> REAL cards.attach_art -> REAL card_scenes fullbleed
renderer -> front.png / inside.png / back.png per card.

    python -m cardgen.demo_offline <dir> <out> labels.json

<dir> holds the photos plus, per template, `<template_id>.png` (front art)
and `<template_id>.spot.png`. labels.json is
{"hero_photos": [...], "hero_pick": {photo: face index}, "labels": {photo: [expr per face]}}
and stands in for the vision labeller, which needs OPENROUTER_API_KEY.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch


def main(src: str, out: str, labels_path: str):
    from PIL import Image
    import numpy as np
    from backend import config, db, studio_library, faces as FC, photo_labels as PL, cards as C, storage
    from backend import card_scenes as S
    from cardgen import engine as E

    src, out = Path(src), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    spec = json.loads(Path(labels_path).read_text())
    tmp = Path(tempfile.mkdtemp())
    with patch.object(config, "DATA", tmp), patch.object(config, "DB_PATH", tmp / "demo.db"), \
         patch.object(storage, "put", lambda local, key: key):
        db.init(); studio_library.init(); FC.ensure_schema(); PL.ensure_schema(); C.init()
        owner, sid = "demo_owner", "sub_hero"
        with db.connect() as c:
            c.execute("INSERT INTO studio_subjects VALUES (?,?,?,?,?)", (sid, owner, "Chris", "person", time.time()))
            for f in sorted(src.glob("*.jpg")):
                from PIL import ImageOps
                im = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
                pid = "pho_" + f.stem
                key = f"demo/{f.name}"
                im.save(C.cached(key), "JPEG")
                c.execute("INSERT INTO photos (id,owner,sha256,r2_key,mime,width,height,bytes,orig_name,created_at,person,source)"
                          " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                          (pid, owner, "sha" + pid, key, "image/jpeg", im.width, im.height, 1, f.name, time.time(), "", "photo"))
                bgr = np.asarray(im)[:, :, ::-1].copy()
                rows = sorted(FC.detect_boxes(bgr, 0.7), key=lambda r: r[0])
                labs = spec["labels"].get(f.stem, [])
                if isinstance(labs, str):
                    labs = [labs] * len(rows)
                for i, row in enumerate(rows):
                    fid = f"face_{f.stem}_{i}"
                    box = [int(v) for v in row[:4]]
                    c.execute("INSERT INTO photo_faces (id,photo_id,box,score,source) VALUES (?,?,?,?,?)",
                              (fid, pid, json.dumps(box), float(row[14]), "yunet"))
                    vec = FC.embed_face(bgr, row)
                    if vec:
                        import struct
                        c.execute("INSERT INTO face_embeddings VALUES (?,?,?,?,?,?,?)",
                                  (fid, pid, owner, "sface128", 128, struct.pack("128f", *vec), time.time()))
                    expr = labs[i] if i < len(labs) else "unknown"
                    row_l = PL.heuristic(box, im.width, im.height)
                    c.execute("INSERT INTO photo_labels (photo_id,face_id,expression,framing,look,eyes_open,sharp,source,model,created_at)"
                              " VALUES (?,?,?,?,?,?,?,?,?,?)",
                              (pid, fid, expr, row_l["framing"], "frontal", 1, 0, "demo", "", time.time()))
                if f.stem in spec["hero_photos"] and rows:
                    hi = spec.get("hero_pick", {}).get(f.stem, 0)
                    c.execute("INSERT INTO photo_subjects VALUES (?,?,?,1,?)", (pid, sid, f"face_{f.stem}_{hi}", "demo"))
                print(f"{f.name}: {len(rows)} faces, labels {labs}")
            c.commit()
            # suggest-then-confirm, like the studio: faces close to the seed hero face get tagged
            import struct
            seeds = [list(struct.unpack("128f", r["vec"])) for r in c.execute(
                "SELECT e.vec FROM face_embeddings e JOIN photo_subjects ps ON ps.face_id=e.face_id WHERE ps.subject_id=?", (sid,))]
            for r in c.execute("SELECT face_id, photo_id, vec FROM face_embeddings").fetchall():
                if c.execute("SELECT 1 FROM photo_subjects WHERE photo_id=?", (r["photo_id"],)).fetchone():
                    continue
                v = list(struct.unpack("128f", r["vec"]))
                best = max([FC.cosine(v, s) for s in seeds] + [0])
                if best >= 0.36:
                    c.execute("INSERT INTO photo_subjects VALUES (?,?,?,1,?)", (r["photo_id"], sid, r["face_id"], "suggest>=0.36"))
                    print(f"  tagged {r['face_id']} as hero (sface {best:.2f})")
            c.commit()

        profile = {"name": "Chris", "relationship": "dad", "interests": ["golf"], "recipient": "Dad",
                   "sender": "Love, Tom x", "surname": "Prior", "tone": "funny"}
        rec = E.recommend(owner, sid, "birthday", profile, label=False)
        print("READY  ", [(r["template_id"], r["photos"]) for r in rec["ready"]])
        print("BLOCKED", [(b["template_id"], b["shortfall"]) for b in rec["blocked"]])
        report = {"recommend": rec, "cards": []}
        for r in rec["ready"]:
            tid = r["template_id"]
            art_p, spot_p = src / f"{tid}.png", src / f"{tid}.spot.png"
            if not art_p.exists():
                continue

            def gen(cap, prompt, refs, art_p=art_p, spot_p=spot_p):
                p = spot_p if cap == "spot" else art_p
                if cap == "upscale":
                    im = Image.open(art_p).convert("RGB")
                    return im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
                return Image.open(p).convert("RGB")

            jid = "cgj_demo_" + tid
            with E._db() as c:
                c.execute("INSERT INTO cardgen_jobs (id,owner,subject_id,template_id,status,created_at,updated_at)"
                          " VALUES (?,?,?,?,'queued',0,0)", (jid, owner, sid, tid))
                c.commit()
            copy = spec.get("copy", {}).get(tid, {})
            E.run(jid, owner, sid, tid, profile, copy, gen=gen)
            j = E.job(owner, jid)
            print(tid, j["status"], j["error"], j["design_id"], "QA:", json.dumps((j["record"].get("qa") or [{}])[-1])[:200])
            if j["status"] != "ready":
                report["cards"].append({"template": tid, "status": j["status"], "error": j["error"]})
                continue
            d = C.record(owner, j["design_id"], j["revision"])
            sp = d["spec"]
            aa = C.assets(owner, sp)
            od = out / tid
            od.mkdir(exist_ok=True)
            S.front(sp, aa, width=1050).save(od / "1_front.jpg", quality=90)
            S.inside(sp, width=2100, assets=aa).convert("RGB").save(od / "2_inside.jpg", quality=90)
            S.back(sp, width=1050, assets=aa).save(od / "3_back.jpg", quality=90)
            report["cards"].append({"template": tid, "status": "ready", "design_id": d["id"], "revision": d["revision"],
                                    "photos": j["record"]["photos"]["roles"], "refs": j["record"]["photos"]["refs"],
                                    "copy": j["record"]["copy"], "qa": j["record"]["qa"],
                                    "spec_keys": sorted(sp), "price": C.card_price()["price"]})
        (out / "report.json").write_text(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main(*sys.argv[1:4])
