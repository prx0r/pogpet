from __future__ import annotations
from dataclasses import dataclass,field,asdict
from datetime import datetime,timezone
from typing import Any

def now_iso(): return datetime.now(timezone.utc).isoformat()

class JsonMixin:
    def to_dict(self)->dict[str,Any]: return asdict(self)

@dataclass
class TemporalClaim(JsonMixin):
    id:str; statement:str; status:str="confirmed"; observed_at:str=field(default_factory=now_iso)
    valid_from:str|None=None; valid_to:str|None=None; source_ids:list[str]=field(default_factory=list)
    tags:list[str]=field(default_factory=list); notes:str=""

@dataclass
class TimelineEntry(JsonMixin):
    id:str; at:str; summary:str; source_ids:list[str]=field(default_factory=list)
    headline:str|None=None; tags:list[str]=field(default_factory=list)

@dataclass
class JokeBlock(JsonMixin):
    id:str; title:str; central_question:str; block_type:str="evergreen"; status:str="active"
    created_at:str=field(default_factory=now_iso); last_updated_at:str=field(default_factory=now_iso)
    tags:list[str]=field(default_factory=list); evergreen_narratives:list[str]=field(default_factory=list)
    source_ids:list[str]=field(default_factory=list); claims:list[TemporalClaim]=field(default_factory=list)
    timeline:list[TimelineEntry]=field(default_factory=list); quote_bank:list[dict]=field(default_factory=list)
    actors:list[dict]=field(default_factory=list); culture_state:dict=field(default_factory=dict)
    comic_structure:dict=field(default_factory=dict); theory_handles:list[str]=field(default_factory=list)
    premise_territories:list[str]=field(default_factory=list); derivation_territories:list[str]=field(default_factory=list)
    connections:list[dict]=field(default_factory=list); open_questions:list[str]=field(default_factory=list)
    update_triggers:list[str]=field(default_factory=list); changelog:list[dict]=field(default_factory=list)

    @classmethod
    def from_dict(cls,d):
        cr=d.get("claims")
        if cr is None: cr=(d.get("reality") or {}).get("claims",[])
        claims=[x if isinstance(x,TemporalClaim) else TemporalClaim(
            id=x.get("id","claim"),statement=x.get("statement",""),status=x.get("status","unknown"),
            observed_at=x.get("observed_at") or now_iso(),valid_from=x.get("valid_from"),valid_to=x.get("valid_to"),
            source_ids=x.get("source_ids",[]),tags=x.get("tags",[]),notes=x.get("notes","")) for x in cr]
        tl=[x if isinstance(x,TimelineEntry) else TimelineEntry(
            id=x.get("id","event"),at=x.get("at",""),summary=x.get("summary",""),
            source_ids=x.get("source_ids",[]),headline=x.get("headline"),tags=x.get("tags",[])) for x in d.get("timeline",[])]
        return cls(id=d["id"],title=d.get("title",d["id"]),central_question=d.get("central_question",""),
            block_type=d.get("block_type","evergreen"),status=d.get("status","active"),
            created_at=d.get("created_at",now_iso()),last_updated_at=d.get("last_updated_at",now_iso()),
            tags=d.get("tags",[]),evergreen_narratives=d.get("evergreen_narratives",[]),source_ids=d.get("source_ids",[]),
            claims=claims,timeline=tl,quote_bank=d.get("quote_bank",[]),actors=d.get("actors",[]),
            culture_state=d.get("culture_state",{}),comic_structure=d.get("comic_structure",{}),
            theory_handles=d.get("theory_handles",[]),premise_territories=d.get("premise_territories",[]),
            derivation_territories=d.get("derivation_territories",[]),connections=d.get("connections",[]),
            open_questions=d.get("open_questions",[]),update_triggers=d.get("update_triggers",[]),changelog=d.get("changelog",[]))

@dataclass
class DynamicState(JsonMixin):
    mood:str="neutral"; energy:float=.6; current_obsessions:list[str]=field(default_factory=list)
    active_threads:list[str]=field(default_factory=list); grudges:dict[str,float]=field(default_factory=dict)
    affinities:dict[str,float]=field(default_factory=dict)

@dataclass
class CharacterGraph(JsonMixin):
    id:str; name:str; species_or_type:str; premise:str
    created_at:str=field(default_factory=now_iso); updated_at:str=field(default_factory=now_iso)
    source_block_ids:list[str]=field(default_factory=list); core:dict=field(default_factory=dict)
    expression:dict=field(default_factory=dict); dynamic_state:DynamicState=field(default_factory=DynamicState)
    world_model:dict=field(default_factory=dict); status_model:dict=field(default_factory=dict)
    knowledge:dict=field(default_factory=dict); perception:dict=field(default_factory=dict)
    action_policy:dict=field(default_factory=dict); comedy:dict=field(default_factory=dict)
    relationships:list[dict]=field(default_factory=list); memory_config:dict=field(default_factory=dict)
    rights:dict=field(default_factory=dict)

    @classmethod
    def from_dict(cls,d):
        dyn=d.get("dynamic_state") or d.get("state") or {}
        if not isinstance(dyn,DynamicState):
            dyn=DynamicState(**{k:v for k,v in dyn.items() if k in DynamicState.__dataclass_fields__})
        identity=d.get("identity_graph",{}); cg=d.get("comedy_graph",d.get("comedy",{})); perf=d.get("performance_seed",{})
        core=d.get("core") or {"facts":identity.get("facts",[]),"worldview":identity.get("worldview",[]),
            "dominant_humour":(cg.get("core_contradictions") or [""])[0],"contradictions":cg.get("core_contradictions",[]),
            "want":identity.get("want",""),"fear":identity.get("fear",""),"blind_spots":identity.get("blind_spots",[])}
        expression=d.get("expression") or {"performance_seed":perf,"vibe":perf.get("vibe","")}
        return cls(id=d["id"],name=d.get("name",d["id"]),species_or_type=d.get("species_or_type","character"),
            premise=d.get("premise",""),created_at=d.get("created_at",now_iso()),updated_at=d.get("updated_at",now_iso()),
            source_block_ids=d.get("source_block_ids",[]),core=core,expression=expression,dynamic_state=dyn,
            world_model=d.get("world_model",{}),status_model=d.get("status_model",{}),knowledge=d.get("knowledge",{}),
            perception=d.get("perception",{}),action_policy=d.get("action_policy",{}),comedy=cg,
            relationships=d.get("relationships",[]),memory_config=d.get("memory_config",{}),rights=d.get("rights",{}))

@dataclass
class SalientItem(JsonMixin):
    ref:str; text:str; score:float; reason:str; kind:str="fact"

@dataclass
class CharacterBlockView(JsonMixin):
    id:str; character_id:str; block_id:str; created_at:str=field(default_factory=now_iso)
    relevance_score:float=0.; accessible_reality:list[str]=field(default_factory=list)
    salience:list[SalientItem]=field(default_factory=list); activated_memories:list[dict]=field(default_factory=list)
    emotional_stakes:list[str]=field(default_factory=list); status_stakes:list[str]=field(default_factory=list)
    first_person_cognition:dict=field(default_factory=dict); third_person_analysis:dict=field(default_factory=dict)
    candidate_operator_ids:list[str]=field(default_factory=list)

@dataclass
class PremiseCandidate(JsonMixin):
    id:str; character_id:str; block_ids:list[str]; statement:str; operator_trace:list[dict]
    created_at:str=field(default_factory=now_iso); truth_mode:str="alternate_interpretation"
    audience_model_before:list[str]=field(default_factory=list); audience_model_after:list[str]=field(default_factory=list)
    factual_grounding_claim_ids:list[str]=field(default_factory=list); derivations:list[str]=field(default_factory=list)
    tags:list[str]=field(default_factory=list); source_lore:dict=field(default_factory=dict)

@dataclass
class GateResult(JsonMixin):
    candidate_id:str; accepted:bool; score:float; hard_vetoes:list[str]=field(default_factory=list)
    dimensions:dict[str,float]=field(default_factory=dict); notes:list[str]=field(default_factory=list)

@dataclass
class InsightMemory(JsonMixin):
    id:str; character_id:str; statement:str; grounded_episode_ids:list[str]
    created_at:str=field(default_factory=now_iso); importance:float=.5; tags:list[str]=field(default_factory=list)
    superseded_by:str|None=None

@dataclass
class Episode(JsonMixin):
    id:str; kind:str; body:dict; observed_at:str=field(default_factory=now_iso)
    valid_at:str|None=None; source_description:str=""; group_id:str="pogtown"; tags:list[str]=field(default_factory=list)
