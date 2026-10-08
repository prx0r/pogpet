import re,hashlib
STOP=set("the a an and or to of in on for with is are was were be been that this it as at by from what who how when why their they them he she his her we you i our your".split())
def toks(s): return [x for x in re.findall(r"[a-z0-9']+",(s or "").lower()) if x not in STOP and len(x)>1]
def jaccard(a,b):
    A=set(toks(a) if isinstance(a,str) else [str(x).lower() for x in a]);B=set(toks(b) if isinstance(b,str) else [str(x).lower() for x in b])
    return len(A&B)/len(A|B) if A and B else 0.
def lexical_overlap(text,terms):
    T=set(toks(text));best=0.
    for term in terms:
        q=set(toks(str(term)))
        if q: best=max(best,len(T&q)/len(q))
    return best
def stable_id(prefix,*parts): return prefix+"_"+hashlib.sha1("|".join(str(x) for x in parts).encode()).hexdigest()[:12]
