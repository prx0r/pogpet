from datetime import datetime,timezone
from .models import InsightMemory
from .text import jaccard,stable_id
class DualMemory:
    def __init__(self,store):self.store=store
    def factual(self,block_id,as_of=None):return self.store.get_block(block_id,as_of)
    def remember_insight(self,character_id,statement,grounded_episode_ids,importance=.5,tags=None):
        m=InsightMemory(id=stable_id("insight",character_id,statement,*grounded_episode_ids),character_id=character_id,
            statement=statement,grounded_episode_ids=grounded_episode_ids,importance=max(0,min(1,importance)),tags=tags or [])
        self.store.add_insight(m);return m
    def retrieve_insights(self,character_id,query,limit=8):
        out=[]
        now=datetime.now(timezone.utc)
        for m in self.store.insights(character_id):
            if m.superseded_by:continue
            try:d=datetime.fromisoformat(m.created_at.replace("Z","+00:00"));days=max(0,(now-d).total_seconds()/86400)
            except:days=999
            rel=jaccard(query,m.statement+" "+" ".join(m.tags));rec=1/(1+days/30)
            out.append((m,.55*rel+.25*m.importance+.2*rec))
        return sorted(out,key=lambda x:x[1],reverse=True)[:limit]
