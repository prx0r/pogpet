from dataclasses import dataclass

@dataclass(frozen=True)
class Operator:
    id:str
    family:str
    instruction:str
    diagnostic:str

REGISTRY={
    'double_interpret':Operator('double_interpret','reframe','Find a second coherent interpretation supported by the same facts; change agency/status if possible.','Same evidence must support both readings.'),
    'status_invert':Operator('status_invert','status','Reverse who appears to control, own, employ, judge, teach, rescue, or depend on whom.','Expose a real dependency.'),
    'identity_contradict':Operator('identity_contradict','identity','Cross a defining identity with a trait/action that undermines it.','Must generate repeat situations.'),
    'rigidify':Operator('rigidify','behavior','Continue a rule or policy after circumstances make it inappropriate.','Character stays internally consistent.'),
    'bisociate':Operator('bisociate','association','Map this situation onto a distant domain with the same relational structure.','Analogy must illuminate.'),
    'split_knowledge':Operator('split_knowledge','dramatic_irony','Give audience and character different information states.','Audience anticipates collision.'),
    'mistake_identity':Operator('mistake_identity','farce','Assign wrong identity then compound rational consequences.','Each consequence follows.'),
    'repeat_variation':Operator('repeat_variation','structure','Repeat a pattern while changing one dimension and heightening.','Pattern learned before break.'),
    'literalize':Operator('literalize','language','Make metaphor/euphemism/abstraction materially true.','Exposes hidden logic.'),
    'unmask':Operator('unmask','identity','Reveal actual role/status under official identity.','Reveal explains behavior.'),
    'self_blindness':Operator('self_blindness','character','Make character exemplify flaw they deny.','Keep sincerity.'),
    'character_violation':Operator('character_violation','expectation','Establish stable trait then violate once.','Needs prior history.'),
    'benign_violation':Operator('benign_violation','affect','Move threat/taboo into enough distance/safety to play.',"Don't trivialize harm."),
    'escalate':Operator('escalate','structure','Derive increasingly consequential domains from one rule.','Each follows logically.'),
    'role_swap':Operator('role_swap','status','Exchange functional roles while situation stays constant.','Expose dependency.'),
    'audience_superiority':Operator('audience_superiority','audience','Let audience see truth character/institution misses.','Avoid arbitrary stupidity.'),
    'mundane_translate':Operator('mundane_translate','reframe','Translate existential/technical event into ordinary human institution.','Clarifies abstract event.'),
    'institutionalize':Operator('institutionalize','world','Derive HR/law/bureaucracy/insurance/forms if premise becomes normal.','Supports recurring world.'),
    'species_translate':Operator('species_translate','perspective','Translate through species goals, senses, energy, mating, predation.','Use biological constraints.'),
    'historical_defamiliarize':Operator('historical_defamiliarize','perspective','Historic character assesses modern norms under accurate period assumptions.','No anachronistic knowledge.'),
    'future_backcast':Operator('future_backcast','perspective','Describe present norm as bizarre future historical custom.','Defamiliarize real behavior.'),
    'alien_ethnography':Operator('alien_ethnography','perspective','Describe humans from behavior without accepting native labels.','Ground observable ritual.'),
    'spiritual_collision':Operator('spiritual_collision','philosophy','Put accurate spiritual diagnosis into socially awkward modern context.','Both worldviews intelligible.'),
    'callback_recontextualize':Operator('callback_recontextualize','structure','Return to earlier element after audience model changed.','Adds new meaning.')
}


def select_operators(character,view,limit=8):
    priors=character.comedy.get("operator_priors",{})
    ids=[x for x in dict.fromkeys(view.candidate_operator_ids+list(priors)) if x in REGISTRY]
    ids.sort(key=lambda x:priors.get(x,.25),reverse=True)
    return [REGISTRY[x] for x in ids[:limit]]
def operator_prompt(op,character,block,view):
    salient="\n".join("- "+x.text for x in view.salience[:8])
    return f"""OPERATOR: {op.id}
RULE: {op.instruction}
DIAGNOSTIC: {op.diagnostic}
CHARACTER: {character.name}
CHARACTER PREMISE: {character.premise}
CORE: {character.core}
SALIENT FACTS/STRUCTURE:
{salient}
JOKEBLOCK: {block.title}
CENTRAL QUESTION: {block.central_question}
Generate a perception-changing premise that could ONLY come from this character.
Do not write a finished punchline. Return premise + 3 logical derivations.
Do not assert disputed/unsupported claims as fact."""
