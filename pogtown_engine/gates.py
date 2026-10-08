from .models import GateResult
from .text import lexical_overlap,jaccard
def _char(c,p):
    terms=[str(c.core.get(k,"")) for k in ("want","fear","dominant_humour")]+[str(x) for x in c.core.get("contradictions",[])]+[str(x) for x in c.perception.get("notices_first",[])]+[str(x) for x in c.comedy.get("recurring_bits",[])]
    s=lexical_overlap(p.statement+" "+" ".join(p.derivations),terms)
    ids={x.get("operator_id") for x in p.operator_trace}
    if ids&{"species_translate","historical_defamiliarize","alien_ethnography","spiritual_collision"}:s+=.22
    return min(1,s)
def _reframe(p):
    a=" ".join(p.audience_model_before);b=" ".join(p.audience_model_after)
    return max(.2,1-jaccard(a,b)) if a and b else .2
def novelty(p,archive):
    return 1-max([jaccard(p.statement,x.statement) for x in archive],default=0)
def gate(c,b,p,archive=None,min_score=.47):
    known={x.id:x for x in b.claims};bad=[i for i in p.factual_grounding_claim_ids if i in known and known[i].status in {"false","unsupported"}]
    dims={"fact_integrity":0 if bad else 1,"character_specificity":_char(c,p),"reframe":_reframe(p),
          "fertility":min(1,len([x for x in p.derivations if str(x).strip()])/5),"novelty":novelty(p,archive or []),
          "compression":1 if len(p.statement)<=180 else max(.15,180/len(p.statement))}
    veto=[]
    if bad:veto.append("FACTUAL_GROUNDING_USES_FALSE_OR_UNSUPPORTED_CLAIM")
    if dims["character_specificity"]<.10:veto.append("CHARACTER_COULD_BE_SWAPPED_FOR_ANYONE")
    if not p.operator_trace:veto.append("NO_OPERATOR_TRACE")
    score=.20*dims["fact_integrity"]+.22*dims["character_specificity"]+.20*dims["reframe"]+.15*dims["fertility"]+.13*dims["novelty"]+.10*dims["compression"]
    return GateResult(p.id,not veto and score>=min_score,round(score,4),veto,{k:round(v,4) for k,v in dims.items()},[] if score>=min_score else ["Below threshold"])
