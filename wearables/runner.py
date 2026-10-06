from __future__ import annotations

import subprocess
from pathlib import Path


def build_variant(*, input_glb, output_glb, items=(), hardware=(),
                  asset_root="data/assets/wearables", blender="blender",
                  repo_root=".", anchors=None, check=True):
    """Normal-Python integration point for backend/server.py or jobs.

    It launches Blender headlessly rather than importing bpy into the web server.
    """
    repo=Path(repo_root)
    cmd=[str(blender),"--background","--python",str(repo/"scripts/wearables_cli.py"),"--","compose",
         "--in",str(input_glb),"--out",str(output_glb),"--asset-root",str(asset_root)]
    for x in items: cmd += ["--item",str(x)]
    for x in hardware: cmd += ["--hardware",str(x)]
    if anchors: cmd += ["--anchors",str(anchors)]
    return subprocess.run(cmd,cwd=str(repo),check=check,text=True,capture_output=True)
