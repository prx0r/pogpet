from __future__ import annotations

import json
from pathlib import Path

from .blender_utils import bpy_mod, import_glb, export_glb
from .manifest import AssetRegistry
from .target import analyse_target, load_overrides
from .headwear import fit_headwear
from .props import fit_prop
from .garments import fit_garment
from .hardware import build_hardware
from .qc import sanity


def _parse_item(token):
    if "@" in token:
        a,s=token.split("@",1); return a.strip(),s.strip()
    return token.strip(),None


def compose(*, input_glb, output_glb, asset_root, items=(), hardware=(), anchors=None,
            report_path=None):
    bpy=bpy_mod(); bpy.ops.wm.read_factory_settings(use_empty=True)
    body=import_glb(input_glb)
    if not body: raise ValueError("input GLB has no meshes")
    profile=analyse_target(body,load_overrides(anchors))
    reg=AssetRegistry(asset_root); reg.scan()
    built=[]; report={"input":str(input_glb),"output":str(output_glb),"profile":profile,"attachments":[]}

    for token in items:
        aid,socket=_parse_item(token); spec=reg.get(aid)
        if spec.kind=="headwear": ob,meta=fit_headwear(spec,profile,socket_name=socket or "headwear")
        elif spec.kind=="garment": ob,meta=fit_garment(spec,profile,body)
        elif spec.kind=="prop": ob,meta=fit_prop(spec,profile,socket_name=socket)
        elif spec.kind=="hardware":
            obs,meta=build_hardware(spec,profile); built.extend(obs)
            report["attachments"].append({"id":aid,"kind":spec.kind,"meta":meta}); continue
        else: raise ValueError(spec.kind)
        built.append(ob); report["attachments"].append({"id":aid,"kind":spec.kind,"meta":meta,"qc":sanity(ob,profile)})

    for aid in hardware:
        spec=reg.get(aid)
        if spec.kind!="hardware": raise ValueError(f"{aid} is not hardware")
        obs,meta=build_hardware(spec,profile); built.extend(obs)
        report["attachments"].append({"id":aid,"kind":"hardware","meta":meta})

    export_glb(output_glb,body+built)
    rp=Path(report_path) if report_path else Path(output_glb).with_suffix(".wearables.json")
    rp.write_text(json.dumps(report,indent=2)+"\n")
    return report
