#!/usr/bin/env python3
"""Inspect an authored GLB; optionally emit a draft motion manifest on stdout."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.motion_contract import MotionError,inspect,author_manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('asset',type=Path)
    p.add_argument('--clip',type=int,help='Clip index for a draft manifest')
    p.add_argument('--rig-id',help='Explicit rig version, for example oddhobb-humanoid-v1')
    p.add_argument('--poster-ms',type=int,default=0)
    args=p.parse_args()
    try:
        result=inspect(args.asset) if args.clip is None else author_manifest(args.asset,args.clip,args.rig_id,args.poster_ms)
    except (MotionError,OSError) as e:p.exit(2,str(e)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
