from __future__ import annotations

import argparse, json, sys


def parser():
    p=argparse.ArgumentParser(prog="oddhobb-wearables")
    sub=p.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("analyse"); a.add_argument("--in",dest="src",required=True); a.add_argument("--anchors"); a.add_argument("--out")
    c=sub.add_parser("compose"); c.add_argument("--in",dest="src",required=True); c.add_argument("--out",required=True); c.add_argument("--asset-root",default="data/assets/wearables"); c.add_argument("--item",action="append",default=[]); c.add_argument("--hardware",action="append",default=[]); c.add_argument("--anchors"); c.add_argument("--report")
    l=sub.add_parser("list"); l.add_argument("--asset-root",default="data/assets/wearables")
    return p


def main(argv=None):
    argv=list(sys.argv[sys.argv.index("--")+1:] if argv is None and "--" in sys.argv else (argv if argv is not None else sys.argv[1:]))
    a=parser().parse_args(argv)
    if a.cmd=="list":
        from .manifest import AssetRegistry
        r=AssetRegistry(a.asset_root); print("\n".join(r.ids())); return 0
    if a.cmd=="analyse":
        import bpy
        from .blender_utils import import_glb
        from .target import analyse_target,load_overrides
        bpy.ops.wm.read_factory_settings(use_empty=True); body=import_glb(a.src)
        doc=analyse_target(body,load_overrides(a.anchors)); txt=json.dumps(doc,indent=2)
        if a.out: open(a.out,"w").write(txt+"\n")
        print(txt); return 0
    if a.cmd=="compose":
        from .compiler import compose
        doc=compose(input_glb=a.src,output_glb=a.out,asset_root=a.asset_root,items=a.item,hardware=a.hardware,anchors=a.anchors,report_path=a.report)
        print(json.dumps(doc,indent=2)); return 0
    return 2
