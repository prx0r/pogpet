import json
from pathlib import Path
from wearables.manifest import AssetRegistry

def test_registry(tmp_path):
    d=tmp_path/"candle"; d.mkdir()
    (d/"asset.json").write_text(json.dumps({"id":"candle","kind":"prop","file":"master.glb"}))
    r=AssetRegistry(tmp_path)
    assert r.get("candle").kind=="prop"
