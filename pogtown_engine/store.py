from pathlib import Path
import json
from .models import *
class JsonTemporalStore:
    def __init__(self,root):
        self.root=Path(root);[ (self.root/d).mkdir(parents=True,exist_ok=True) for d in ("blocks","characters","insights") ]
        self.episodes=self.root/"episodes.jsonl"
    def _append(self,p,row):
        p.parent.mkdir(parents=True,exist_ok=True)
        with p.open("a",encoding="utf-8") as f:f.write(json.dumps(row,ensure_ascii=False)+"\n")
    def add_episode(self,e):self._append(self.episodes,e.to_dict());return e
    def iter_episodes(self,kind=None,group_id=None):
        if not self.episodes.exists():return
        for line in self.episodes.read_text(encoding="utf-8").splitlines():
            x=json.loads(line)
            if kind and x.get("kind")!=kind:continue
            if group_id and x.get("group_id")!=group_id:continue
            yield x
    def put_block(self,b):
        b.last_updated_at=now_iso();obs=now_iso();self._append(self.root/"blocks"/f"{b.id}.jsonl",{"observed_at":obs,"payload":b.to_dict()})
        self.add_episode(Episode(id=f"block:{b.id}:{obs}",kind="joke_block_snapshot",body=b.to_dict(),source_description="JokeBlock snapshot",tags=b.tags))
    def get_block(self,bid,as_of=None):
        p=self.root/"blocks"/f"{bid}.jsonl"
        if not p.exists():return None
        rows=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
        if as_of:rows=[r for r in rows if r["observed_at"]<=as_of]
        return JokeBlock.from_dict(sorted(rows,key=lambda x:x["observed_at"])[-1]["payload"]) if rows else None
    def put_character(self,c):
        c.updated_at=now_iso();self._append(self.root/"characters"/f"{c.id}.jsonl",{"observed_at":now_iso(),"payload":c.to_dict()})
    def get_character(self,cid,as_of=None):
        p=self.root/"characters"/f"{cid}.jsonl"
        if not p.exists():return None
        rows=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
        if as_of:rows=[r for r in rows if r["observed_at"]<=as_of]
        return CharacterGraph.from_dict(sorted(rows,key=lambda x:x["observed_at"])[-1]["payload"]) if rows else None
    def add_insight(self,m):self._append(self.root/"insights"/f"{m.character_id}.jsonl",m.to_dict())
    def insights(self,cid):
        p=self.root/"insights"/f"{cid}.jsonl"
        return [InsightMemory(**json.loads(x)) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []
