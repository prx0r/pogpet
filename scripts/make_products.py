#!/usr/bin/env python3
"""Product pipeline CLI: any person, pet or character -> every Prodigi product.

  python3 scripts/make_products.py add-subject --name Jenny --photos <dir|file|url ...> \\
          [--kind person|pet|character] [--relationship mum] [--owner local_owner]
  python3 scripts/make_products.py run --subject <id> --products all|mug,tote \\
          [--age 70] [--recipient Mum] [--style classic] [--out DIR] [--store]
  python3 scripts/make_products.py subjects            # list registered subjects

Same code as REST (POST /api/subjects/intake, POST /api/products/make) and MCP
(oddhobb_subject_add, oddhobb_product_make): subject_intake.add_subject and
product_art.make_all. Data lives where the backend's config points (FIGG_DATA,
RCLONE/R2_REMOTE), exactly like the server. No per-subject code anywhere.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _owner(c, handle):
    from backend import db
    u = db.get_user_by_handle(c, handle) if hasattr(db, "get_user_by_handle") else None
    if not u:
        u = db.create_user(c, handle, password=os.urandom(12).hex())
        c.commit()
    return u["handle"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--owner", default=os.environ.get("ODD_OWNER", "local_owner"))
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("add-subject", help="register a person/pet/character from photos")
    a.add_argument("--name", required=True)
    a.add_argument("--photos", nargs="+", required=True, help="files, folders, http(s) URLs or pho_ ids")
    a.add_argument("--kind", default="person", choices=["person", "pet", "character"])
    a.add_argument("--relationship", default="")
    a.add_argument("--interests", default="", help="comma separated")
    a.add_argument("--subject", default="", help="add photos to an existing subject id")
    r = sp.add_parser("run", help="make products for a subject")
    r.add_argument("--subject", required=True)
    r.add_argument("--products", default="all")
    r.add_argument("--age", type=int, default=0)
    r.add_argument("--recipient", default=None)
    r.add_argument("--style", default=None)
    r.add_argument("--out", default="", help="write <product>_{print,preview}.jpg here")
    r.add_argument("--store", action="store_true", help="also store + record them (public proof URLs, like REST)")
    sp.add_parser("subjects", help="list subjects")
    args = ap.parse_args(argv)

    from backend import db, product_art, server
    db.init()
    with db.connect() as c:
        owner = _owner(c, args.owner)
    if args.cmd == "add-subject":
        from backend import subject_intake
        res = subject_intake.add_subject(server.app, owner, args.name, args.photos, kind=args.kind,
                                         relationship=args.relationship,
                                         interests=[x.strip() for x in args.interests.split(",") if x.strip()],
                                         subject_id=args.subject)
    elif args.cmd == "subjects":
        with db.connect() as c:
            rows = [dict(x) for x in c.execute(
                "SELECT s.id, s.name, s.kind, (SELECT count(*) FROM photo_subjects ps WHERE ps.subject_id=s.id) AS tags"
                " FROM studio_subjects s WHERE s.owner=? ORDER BY s.created_at", (owner,))]
        res = {"ok": True, "owner": owner, "subjects": rows}
    else:
        prods = product_art.product_ids() if args.products == "all" else [p.strip() for p in args.products.split(",")]
        if args.store:
            res = product_art.make_and_store(owner, args.subject, prods, age=args.age, recipient=args.recipient,
                                             style=args.style)
        else:
            out = args.out or str(product_art.default_out_dir(owner, args.subject))
            res = {"ok": True, "out_dir": out,
                   "products": product_art.make_all(owner, args.subject, age=args.age, recipient=args.recipient,
                                                    style=args.style, products=prods, out_dir=out)}
            res["ok"] = any(v.get("ok") for v in res["products"].values())
    print(json.dumps(res, indent=1, default=str))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
