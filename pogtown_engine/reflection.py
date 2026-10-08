def reflect_from_performance(character,memory,traces,min_events=3):
    if len(traces)<min_events:return []
    buckets={}
    for t in traces:
        score=float((t.get("response") or {}).get("engagement_score",0) or 0)
        for tag in (t.get("lineage") or {}).get("operator_ids",[]):buckets.setdefault("operator:"+tag,[]).append(score)
        for tag in (t.get("lineage") or {}).get("tags",[]):buckets.setdefault("tag:"+tag,[]).append(score)
    out=[]
    for k,v in buckets.items():
        if len(v)<2:continue
        out.append(memory.remember_insight(character.id,f"{character.name}: {k} mean engagement {sum(v)/len(v):.2f} over {len(v)} traces.",
            [str(x.get("id","")) for x in traces],min(1,.4+len(v)/10),["performance",k]))
    return out
