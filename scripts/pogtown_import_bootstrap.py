#!/usr/bin/env python3
from pathlib import Path
import json,sys
from pogtown_engine.models import JokeBlock
from pogtown_engine.store import JsonTemporalStore
if len(sys.argv)<3:raise SystemExit("usage: pogtown_import_bootstrap.py <block-dir> <store-dir>")
st=JsonTemporalStore(sys.argv[2]);n=0
for p in Path(sys.argv[1]).glob("*.json"):st.put_block(JokeBlock.from_dict(json.loads(p.read_text())));n+=1
print("imported",n)
