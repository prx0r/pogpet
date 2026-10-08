def character_to_freaktown(c):
    perf=c.expression.get("performance_seed",{})
    return {"name":c.name,"species":c.species_or_type,"premise":c.premise,"vibe":c.expression.get("vibe",""),
      "voice":c.expression.get("voice",{}),"persona":{"deal":c.core.get("dominant_humour") or c.premise,"facts":c.core.get("facts",[]),
      "interview_style":c.expression.get("interview_style","character-specific, internally consistent")},
      "profile":{"pace":perf.get("pace",.95),"movement":perf.get("movement",.3),"eye_contact":perf.get("eye_contact",.7),
      "energy":perf.get("energy",c.dynamic_state.energy),"punchline_hold_ms":perf.get("punchline_hold_ms",800),"gesture_frequency":perf.get("gesture_frequency",.3)},
      "actions":c.expression.get("actions",{})}
def trajectory_to_delivery(t,spoken_lines=None):
    spoken_lines=spoken_lines or {};beats=[]
    for s in t.get("steps",[]):
        role="callback" if s["kind"]=="callback" else ("closer" if s["kind"]=="closer" else "setup")
        beats.append({"id":f"beat-{s['order']}","role":role,"text":spoken_lines.get(s["ref_id"],f"[WRITE/RENDER FROM {s['ref_id']}]"),
          "speech":{"pace":1.0,"emphasis":[]},"performance":{"expression":"deadpan","gesture":"hold still","look":"audience"},"pause_after_ms":800 if role in {"callback","closer"} else 450})
    return {"version":"freaktown.delivery.v1","profile":{},"voice":{},"beats":beats}
