from .text import stable_id,jaccard
from .models import now_iso
def assemble(character_id,candidates,target_seconds=300):
    if not candidates:return {"version":"pogtown.set_trajectory.v2","id":stable_id("traj",character_id,"empty"),"performer_id":character_id,"steps":[]}
    chosen=[candidates[0]];rem=candidates[1:]
    while rem and len(chosen)<5:
        rem.sort(key=lambda p:jaccard(" ".join(chosen[-1].tags)," ".join(p.tags)),reverse=True);chosen.append(rem.pop(0))
    steps=[{"order":i,"kind":"premise" if i==1 else "derivation_thread","ref_id":p.id,
            "function":"establish worldview" if i==1 else "heighten/broaden worldview","audience_before":p.audience_model_before,
            "audience_after":p.audience_model_after,"delivery_intent":"character-specific"} for i,p in enumerate(chosen,1)]
    if len(chosen)>2:steps.append({"order":len(steps)+1,"kind":"callback","ref_id":chosen[0].id,"function":"recontextualize opening","audience_before":chosen[-1].audience_model_after,"audience_after":chosen[0].audience_model_after,"delivery_intent":"short callback"})
    return {"version":"pogtown.set_trajectory.v2","id":stable_id("traj",character_id,*[x.id for x in chosen]),"title":"Auto trajectory","performer_id":character_id,
            "created_at":now_iso(),"goal":"Build a worldview, not a bag of jokes.","steps":steps,"callbacks":[],"target_duration_seconds":target_seconds,"compile_target":"freaktown.delivery.v1"}
