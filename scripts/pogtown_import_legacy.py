#!/usr/bin/env python3
from pathlib import Path
import json,sys
from pogtown_engine.adapters.pogpet import legacy_premise_to_block
from pogtown_engine.store import JsonTemporalStore
if len(sys.argv)<3:raise SystemExit("usage: pogtown_import_legacy.py <pack.json> <store-dir>")
data=json.loads(Path(sys.argv[1]).read_text());store=JsonTemporalStore(sys.argv[2]);n=0
def walk(x,fam=None):
    global n
    if isinstance(x,dict):
        if "source_lore" in x and ("text" in x or "id" in x):store.put_block(legacy_premise_to_block(x,fam));n+=1
        else:
            f=x.get("family") or x.get("id") or fam
            for v in x.values():walk(v,f)
    elif isinstance(x,list):
        for v in x:walk(v,fam)
walk(data);print("imported",n)
