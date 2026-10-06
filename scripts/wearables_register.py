#!/usr/bin/env python3
"""Register a downloaded Meshy/other GLB once; fitting stays local thereafter."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from wearables.manifest import install_asset

p=argparse.ArgumentParser()
p.add_argument("--asset-root",default="data/assets/wearables")
p.add_argument("--id",required=True); p.add_argument("--kind",choices=["headwear","garment","prop","hardware"],required=True)
p.add_argument("--glb"); p.add_argument("--glb-url"); p.add_argument("--label")
p.add_argument("--socket",default="hand_right"); p.add_argument("--size-ratio",type=float,default=.25)
p.add_argument("--grip",default="0.5,0.5,0.5",help="bbox-normalised XYZ")
p.add_argument("--source-name",default="Meshy"); p.add_argument("--source-url",default="")
a=p.parse_args()
fit={}
if a.kind=="prop":
    fit={"socket":a.socket,"size_ratio":a.size_ratio,"grip_normalized":[float(x) for x in a.grip.split(",")]}
manifest={"label":a.label or a.id.replace("_"," ").title(),"fit":fit,"source":{"name":a.source_name,"url":a.source_url}}
out=install_asset(asset_root=a.asset_root,asset_id=a.id,kind=a.kind,glb=a.glb,glb_url=a.glb_url or "",manifest=manifest)
print(out)
