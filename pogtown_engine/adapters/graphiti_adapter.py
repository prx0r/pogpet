import json
from datetime import datetime
from ..models import Episode
class GraphitiAdapter:
    """Optional mirror. Canonical Pogtown JSON remains source of truth."""
    def __init__(self,graphiti):self.graphiti=graphiti
    @classmethod
    def neo4j(cls,uri,user,password,**kw):
        from graphiti_core import Graphiti
        return cls(Graphiti(uri,user,password,**kw))
    async def initialize(self):await self.graphiti.build_indices_and_constraints()
    async def add_episode(self,e):
        try:
            from graphiti_core.nodes import EpisodeType
            source=EpisodeType.json
        except ImportError:
            source="json"
        ref=datetime.fromisoformat((e.valid_at or e.observed_at).replace("Z","+00:00"))
        return await self.graphiti.add_episode(name=e.id,episode_body=json.dumps(e.body,ensure_ascii=False),source=source,
          source_description=e.source_description or e.kind,reference_time=ref,group_id=e.group_id)
    async def search(self,q):return await self.graphiti.search(q)
    async def close(self):await self.graphiti.close()
