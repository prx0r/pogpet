from .models import *
from .relevance import relevance,character_terms
from .text import lexical_overlap,stable_id
def _flat(v):
    if isinstance(v,dict):
        for x in v.values():yield from _flat(x)
    elif isinstance(v,list):
        for x in v:yield from _flat(x)
    elif isinstance(v,str):yield v
def build_character_block_view(character,block,memory=None,max_salience=10):
    terms=character_terms(character);sal=[];accessible=[]
    for c in block.claims:
        if c.status in {"false","unsupported"}:continue
        accessible.append(c.statement);s=.25+.75*lexical_overlap(c.statement,terms)
        if c.status in {"unknown","disputed","viral_unverified"}:s*=.7
        sal.append(SalientItem(c.id,c.statement,min(1,s),"overlaps character drives/worldview" if s>.35 else "block reality","claim"))
    for key,vals in block.comic_structure.items():
        for i,text in enumerate(_flat(vals)):
            s=.2+.8*lexical_overlap(text,terms)
            if s>.25:sal.append(SalientItem(f"structure:{key}:{i}",text,min(1,s),f"comic structure intersects character ({key})","structure"))
    sal=sorted(sal,key=lambda x:x.score,reverse=True)[:max_salience]
    activated=[]
    if memory:
        q=block.title+" "+block.central_question+" "+" ".join(x.text for x in sal[:5])
        for m,s in memory.retrieve_insights(character.id,q):
            if s>.15:activated.append({"memory_id":m.id,"statement":m.statement,"score":round(s,4)})
    priors=character.comedy.get("operator_priors",{})
    ops=sorted(set(block.theory_handles)|set(priors),key=lambda o:priors.get(o,.25),reverse=True)[:10]
    return CharacterBlockView(
        id=stable_id("view",character.id,block.id,block.last_updated_at),character_id=character.id,block_id=block.id,
        relevance_score=relevance(character,block),accessible_reality=accessible,salience=sal,activated_memories=activated,
        emotional_stakes=([character.core.get("fear")] if character.core.get("fear") else [])+list(character.core.get("contradictions",[]))[:3],
        status_stakes=list(character.status_model.get("status_sensitivities",[])),
        first_person_cognition={"what_i_notice":[x.text for x in sal[:5]],"what_this_reminds_me_of":[x["statement"] for x in activated[:4]],
            "what_i_want":character.core.get("want",""),"what_i_fear":character.core.get("fear",""),
            "my_blind_spots":character.core.get("blind_spots",[]),"my_default_strategy":character.action_policy.get("default_strategy","")},
        third_person_analysis={"dominant_humour":character.core.get("dominant_humour",""),"character_contradictions":character.core.get("contradictions",[]),
            "knowledge_boundary":character.knowledge.get("knowledge_boundary",""),"block_contradictions":block.comic_structure.get("contradictions",[]),
            "block_script_oppositions":block.comic_structure.get("script_oppositions",[])},
        candidate_operator_ids=ops)
