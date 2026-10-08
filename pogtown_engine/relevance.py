from .models import JokeBlock,CharacterGraph
from .text import lexical_overlap
def _flat(v):
    if isinstance(v,dict):
        for x in v.values():yield from _flat(x)
    elif isinstance(v,list):
        for x in v:yield from _flat(x)
    elif isinstance(v,str):yield v
def character_terms(c):
    x=[c.premise,c.species_or_type]+list(_flat(c.core))+list(_flat(c.world_model))+list(_flat(c.status_model))+list(_flat(c.perception))+list(_flat(c.comedy))
    return [i for i in x if i]+c.dynamic_state.current_obsessions+c.dynamic_state.active_threads
def block_text(b):
    x=[b.title,b.central_question,*b.tags,*b.evergreen_narratives]+[c.statement for c in b.claims]+list(_flat(b.comic_structure))+b.premise_territories+b.derivation_territories
    return " ".join(str(i) for i in x)
def relevance(c,b):
    bt=block_text(b);terms=character_terms(c);lex=lexical_overlap(bt,terms)
    tags=set(x.lower() for x in b.tags+b.evergreen_narratives);ints=set(x.lower() for x in c.perception.get("notices_first",[])+c.dynamic_state.current_obsessions+c.dynamic_state.active_threads)
    tag=len(tags&ints)/max(1,len(tags|ints)) if ints else 0
    aff=max([c.dynamic_state.affinities.get(b.id,0.)]+[c.dynamic_state.affinities.get(t,0.) for t in tags])
    avoid=max([c.dynamic_state.grudges.get("avoid:"+b.id,0.)]+[c.dynamic_state.grudges.get("avoid:"+t,0.) for t in tags])
    return max(0.,min(1.,.55*lex+.25*tag+.25*aff-.2*avoid))
def should_wake(c,b,threshold=.18):return relevance(c,b)>=threshold
