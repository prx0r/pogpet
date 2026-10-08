REQUIRED={"character_id","source_work","source_year","jurisdictions","allowed_traits","excluded_later_traits","trademark_notes","source_links"}
def validate_rights_record(x):return [f"missing:{k}" for k in REQUIRED if k not in x]
def generation_constraints(x):
    e=validate_rights_record(x)
    if e:raise ValueError(", ".join(e))
    return f"Use only allowed source-edition traits: {x['allowed_traits']}. Do not use later protected traits: {x['excluded_later_traits']}. Trademark caution: {x['trademark_notes']}. Use an original voice/performance."
