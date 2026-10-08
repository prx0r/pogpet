from ..models import *
from ..text import stable_id
def coser_like_to_character(s,rights=None):
    name=s.get("name") or s.get("character") or "Character"
    return CharacterGraph(id=s.get("id") or stable_id("char",name),name=name,species_or_type=s.get("species_or_type","human"),
      premise=s.get("premise",f"{name} extracted from source action/choice history"),
      core={"facts":s.get("facts",[]),"want":s.get("want",""),"fear":s.get("fear",""),"need":s.get("need",""),
            "dominant_humour":s.get("dominant_humour",""),"blind_spots":s.get("blind_spots",[]),"contradictions":s.get("contradictions",[])},
      expression=s.get("expression",{}),world_model={"believes":s.get("beliefs",[]),"doubts":s.get("doubts",[]),"misunderstands":s.get("misunderstands",[])},
      knowledge={"knows":s.get("knows",[]),"does_not_know":s.get("does_not_know",[]),"knowledge_boundary":s.get("knowledge_boundary","")},
      perception={"notices_first":s.get("notices_first",[]),"ignores":s.get("ignores",[])},action_policy=s.get("action_policy",{}),
      comedy={"operator_priors":s.get("operator_priors",{}),"recurring_bits":[],"comic_blindspots":s.get("blind_spots",[])},
      relationships=s.get("relationships",[]),rights=rights or {})
def her_reasoning_record(character,scenario,first_person,third_person,spoken):
    return {"character_id":character.id,"scenario":scenario,"third_person_analysis":third_person,"first_person_cognition":first_person,"spoken_material":spoken}
