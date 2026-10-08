from ..models import *
from ..text import stable_id
def legacy_premise_to_block(p,family=None):
    lore=p.get("source_lore") or {};family=family or p.get("family","legacy")
    bid="legacy_"+stable_id("block",family,lore.get("event",""),lore.get("phrase",""))
    claim=TemporalClaim(stable_id("claim",lore.get("event","")),lore.get("event") or p.get("text",""),
        "confirmed" if lore.get("event") else "unknown",notes="Imported from pogpet source_lore; validate against canonical source catalog.")
    tl=[TimelineEntry(stable_id("evt",bid,lore["date"]),str(lore["date"]),lore.get("event",""))] if lore.get("date") else []
    return JokeBlock(id=bid,title=(lore.get("phrase") or p.get("id") or family)[:120],central_question=lore.get("recognition") or "Why is this recognizable?",
      block_type="event",tags=list(dict.fromkeys((p.get("topics") or [])+[family])),claims=[claim],timeline=tl,
      culture_state={"public_frames":[],"camps":[],"meme_vocabulary":[lore.get("phrase","")],"historical_analogues":[],"emotions":[],"discourse_notes":[lore.get("community","")]},
      comic_structure={"contradictions":[],"identity_collisions":[],"status_relations":[],"script_oppositions":[],"knowledge_gaps":[],"euphemisms":[],"ironic_truths":[]},
      premise_territories=[p.get("text","")],changelog=[{"at":now_iso(),"change":"Imported from pogpet source_lore","supersedes":None}])
def candidate_to_pogpet_premise(p,family,format="single_panel"):
    return {"family":family,"format":format,"id":p.id,"source_lore":p.source_lore,"text":p.statement,"topics":list(dict.fromkeys(p.tags))}
class PogpetPerformanceAdapter:
    def __init__(self):
        try:from backend.creative import performance
        except Exception:performance=None
        self.performance=performance
    def record_post(self,p,family,platform,post_ref,format="single_panel"):
        if not self.performance:raise RuntimeError("backend.creative.performance not importable; run inside pogpet")
        return self.performance.record_post(premise_id=p.id,family=family,platform=platform,post_ref=post_ref,format=format)
    def record_metrics(self,**kw):
        if not self.performance:raise RuntimeError("backend.creative.performance not importable; run inside pogpet")
        return self.performance.record_metrics(**kw)
