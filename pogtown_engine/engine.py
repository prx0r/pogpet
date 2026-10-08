from .store import JsonTemporalStore
from .memory import DualMemory
from .relevance import relevance
from .views import build_character_block_view
from .miner import mine
from .gates import gate
from .trajectory import assemble
class PogtownEngine:
    def __init__(self,root,generator=None):self.store=JsonTemporalStore(root);self.memory=DualMemory(self.store);self.generator=generator;self.archive=[]
    def ingest_block(self,b):self.store.put_block(b);return b
    def ingest_character(self,c):self.store.put_character(c);return c
    def wake(self,c,b,threshold=.18):
        rel=relevance(c,b)
        if rel<threshold:return {"woke":False,"relevance":rel,"view":None,"candidates":[],"accepted":[]}
        v=build_character_block_view(c,b,self.memory);cs=mine(c,b,v,self.generator);gs=[gate(c,b,p,self.archive) for p in cs];acc=[p for p,g in zip(cs,gs) if g.accepted];self.archive+=acc
        return {"woke":True,"relevance":rel,"view":v,"candidates":cs,"gate_results":gs,"accepted":acc}
    def work_room(self,characters,b,threshold=.18):
        rows=[]
        for c in characters:
            r=self.wake(c,b,threshold)
            if r["woke"]:rows.append({"character":c,"result":r})
        return {"block":b,"workers":rows}
    def plan_set(self,cid,candidates,seconds=300):return assemble(cid,candidates,seconds)
