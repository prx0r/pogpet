from .views import build_character_block_view
def social_scenario(a,b,block,memory=None,goal_a="",goal_b=""):
    va=build_character_block_view(a,block,memory);vb=build_character_block_view(b,block,memory)
    return {"version":"pogtown.social_scenario.v1","block_id":block.id,
      "participants":[{"character_id":a.id,"private_goal":goal_a or f"defend {a.name}'s worldview","salience":[x.text for x in va.salience[:5]]},
                      {"character_id":b.id,"private_goal":goal_b or f"defend {b.name}'s worldview","salience":[x.text for x in vb.salience[:5]]}],
      "collision":{"a_notices":va.first_person_cognition["what_i_notice"],"b_notices":vb.first_person_cognition["what_i_notice"],
                   "relationship_edges":[x for x in a.relationships if x.get("to")==b.id]+[x for x in b.relationships if x.get("to")==a.id]}}
