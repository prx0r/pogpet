from .models import PremiseCandidate
from .operators import select_operators,operator_prompt
from .text import stable_id
SCHEMA={"premise":"string","audience_before":["string"],"audience_after":["string"],"derivations":["string"],"truth_mode":"alternate_interpretation"}
def _lore(b):
    return {"event":b.timeline[-1].summary if b.timeline else b.title,
            "phrase":b.quote_bank[0].get("text","") if b.quote_bank else "",
            "date":b.timeline[-1].at if b.timeline else b.last_updated_at[:10],
            "community":", ".join(b.tags[:4]),"recognition":b.central_question}
def mine(character,block,view,generator=None,per_operator=2,max_candidates=20):
    out=[];ops=select_operators(character,view,10)
    if generator:
        sys="You mine comedy premises. Premise = perception shift, not punchline. Preserve fact integrity and character necessity."
        for op in ops:
            for _ in range(per_operator):
                try:d=generator.generate_json(sys,operator_prompt(op,character,block,view),SCHEMA)
                except Exception:continue
                s=str(d.get("premise","")).strip()
                if not s:continue
                out.append(PremiseCandidate(id=stable_id("prem",character.id,block.id,op.id,s),character_id=character.id,block_ids=[block.id],statement=s,
                    operator_trace=[{"operator_id":op.id,"effect":d.get("effect","")}],truth_mode=d.get("truth_mode","alternate_interpretation"),
                    audience_model_before=d.get("audience_before",[]),audience_model_after=d.get("audience_after",[]),
                    factual_grounding_claim_ids=[x.ref for x in view.salience if x.kind=="claim"][:5],derivations=d.get("derivations",[])[:6],
                    tags=[op.id,*block.tags[:5]],source_lore=_lore(block)))
                if len(out)>=max_candidates:return out
    else:
        for op in ops:
            for territory in block.premise_territories[:per_operator]:
                s=f"{character.name} angle: {territory}"
                out.append(PremiseCandidate(id=stable_id("prem",character.id,block.id,op.id,s),character_id=character.id,block_ids=[block.id],statement=s,
                    operator_trace=[{"operator_id":op.id,"effect":"deterministic bootstrap seed"}],
                    audience_model_before=[block.central_question],audience_model_after=[territory],
                    factual_grounding_claim_ids=[x.ref for x in view.salience if x.kind=="claim"][:5],
                    derivations=block.derivation_territories[:4],tags=[op.id,*block.tags[:5]],source_lore=_lore(block)))
                if len(out)>=max_candidates:return out
    return out
