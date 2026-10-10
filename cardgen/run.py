"""The agent loop: person + occasion in, N finished cards out.

    python -m cardgen.run make --subject <id> --occasion birthday --n 4

Steps per card: cast -> write -> generate -> QA (fix, max 2) -> spot -> upscale -> impose -> freeze.
The LLM (copy) and image calls go through providers.run; everything is recorded
for provenance so checkout reproduces exactly what was previewed.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path

from . import photos as P, providers, qa, impose

TEMPLATES = Path(__file__).parent / "templates"


def load_templates() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(TEMPLATES.glob("*.json"))]


def rank(templates, profile: dict, occasion: str):
    interests = set(profile.get("interests", []))
    tone = profile.get("tone", "funny")
    out = []
    for t in templates:
        if occasion not in t["occasions"]:
            continue
        s = 1.0 + 2.0 * len(interests & set(t["interests"])) + (0.5 if tone in t["tones"] else 0)
        out.append((s, t))
    return [t for _, t in sorted(out, key=lambda x: -x[0])]


def prompt_for(t: dict, copy: dict, names: dict) -> str:
    scene = t["scene"].format(**names)
    letters = "; ".join(f'"{copy[k]}"' for k in t["qa"]["text_only"])
    return (f"Portrait 5:7 greeting card front, full bleed. {scene} Style: {t['style']}. "
            f"Likeness of every person from the reference photos must be exact. "
            f"The ONLY lettering on the image, integrated into the design: {letters}. "
            f"Leave room for it at the top. {t['negative']}.")


def write_copy(t: dict, profile: dict, llm) -> dict:
    """llm(prompt) -> json. Returns {title, sub|bubble, inside} inside the template limits."""
    lim = {k: v["max"] for k, v in t["copy"].items()}
    ask = (f"Write card copy for {profile['name']} ({profile.get('relationship','')}), "
           f"interests {profile.get('interests')}, tone {profile.get('tone','funny')}. "
           f"Template: {t['id']}. Style anchors: {json.dumps({k: v['examples'] for k, v in t['copy'].items()})}. "
           f"Return JSON with keys {list(lim)}; hard limits {lim}. One joke, not cringe.")
    c = llm(ask)
    for k, m in lim.items():
        if len(c.get(k, "")) > m:
            raise ValueError(f"{k} over {m}")
    return c


def make_one(t, profile, index: list, photo_url, llm, outdir: Path, message_sig: str):
    cast = P.cast(t, index, profile["subject_id"])
    if not cast:
        return None
    copy = write_copy(t, profile, llm)
    names = {"hero": "the man from the reference photos", "partner": "the woman from the reference photos",
             "place": profile.get("place", "the city at dusk"), "hero_prop": profile.get("prop", "a golf club"),
             "pet": "the pet from the reference photos"}
    refs = [photo_url(pid) for pid in cast["refs"]]
    prov = []
    art = providers.run("identity_scene", prompt_for(t, copy, names), refs); prov.append(art)
    expected = [copy[k] for k in t["qa"]["text_only"]]
    for attempt in range(3):
        local = download(art["url"], outdir / f"front_{attempt}.png")
        ok_t, d_t = qa.text_gate(str(local), expected)
        if ok_t:
            break
        if attempt == 2:
            return {"status": "qa_failed", "detail": d_t}
        fix = qa.FIX_PROMPTS["extra_text"].format(keep=" and ".join(f'"{e}"' for e in expected))
        art = providers.run("edit_fix", fix, [art["url"]]); prov.append(art)
    spot = providers.run("identity_scene",
                         f"Small spot illustration in the exact style of the reference: {t['spot'].format(**names)}, "
                         f"centred on a plain flat off-white background #FBF7EE, lots of space. No text.", [art["url"]])
    big = providers.run("upscale", "", [art["url"]]); prov += [spot, big]
    f_png = download(big["url"], outdir / "front_print.png")
    s_png = download(spot["url"], outdir / "spot.png")
    impose.build(f_png, s_png, copy["inside"], message_sig, profile.get("recipient", ""), outdir)
    rev = {"template": t["id"], "photos": cast["refs"], "copy": copy, "providers": prov,
           "art_sha": hashlib.sha256(Path(f_png).read_bytes()).hexdigest()}
    (outdir / "revision.json").write_text(json.dumps(rev, indent=2))
    return rev


def download(url: str, path: Path) -> Path:
    import urllib.request
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(urllib.request.urlopen(url, timeout=120).read())
    return path
